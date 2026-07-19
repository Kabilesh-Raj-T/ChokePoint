"""Risk analysis engine for ChokePoint topologies."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from chokepoint.graph import GraphAnalyzer, GraphBuilder
from chokepoint.models import Edge, Node, NodeType, Relationship, Topology
from chokepoint.models.topology import Metadata

MIN_SHARED_DEPENDENTS = 2
HUMAN_JOIN_PAIR_COUNT = 2
MAX_EDGE_EVIDENCE = 5


class ConfidenceLevel(StrEnum):
    """Confidence levels for risk findings."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceKind(StrEnum):
    """Kinds of evidence attached to a risk finding."""

    EXPLICIT_CONFIG = "explicit_config"
    INFERRED = "inferred"
    GRAPH_ANALYSIS = "graph_analysis"
    HEURISTIC = "heuristic"


class FindingAssessment(StrEnum):
    """Human review status implied by a risk finding."""

    CONFIRMED = "confirmed"
    LIKELY = "likely"
    MODELING_ARTIFACT = "modeling_artifact"
    NEEDS_REVIEW = "needs_review"


class Evidence(BaseModel):
    """Evidence explaining why ChokePoint emitted a finding."""

    model_config = ConfigDict(frozen=True)

    parser: str
    source: str | None = None
    line: int | None = Field(default=None, ge=1)
    kind: EvidenceKind
    subject: str
    detail: str


class RiskLevel(StrEnum):
    """Risk severity levels emitted by the analysis engine."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskCategory(StrEnum):
    """Infrastructure dependency categories used by risk rules."""

    DNS = "dns"
    IDENTITY = "identity"
    CDN = "cdn"
    SECRETS_MANAGER = "secrets_manager"
    MONITORING = "monitoring"
    NETWORKING = "networking"
    CI_CD = "ci_cd"
    EMAIL = "email"
    SINGLE_SERVICE_ARTICULATION = "single_service_articulation"


class DependencyChain(BaseModel):
    """Dependency chain from an impacted node to a risky dependency."""

    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    path: tuple[str, ...]


class RiskFinding(BaseModel):
    """One risk finding in a ChokePoint risk report."""

    model_config = ConfigDict(frozen=True)

    node_id: str
    node_name: str
    provider: str
    category: RiskCategory
    risk_level: RiskLevel
    criticality: RiskLevel
    risk_score: int = Field(ge=0, le=100)
    blast_radius: int = Field(ge=0)
    impacted_nodes: tuple[str, ...]
    impacted_providers: tuple[str, ...]
    dependency_chain: tuple[DependencyChain, ...]
    confidence: ConfidenceLevel
    assessment: FindingAssessment
    evidence: tuple[Evidence, ...] = ()
    explanation: str


class RiskReport(BaseModel):
    """Structured ChokePoint risk report."""

    model_config = ConfigDict(frozen=True)

    risk_score: int = Field(ge=0, le=100)
    finding_count: int = Field(ge=0)
    findings: tuple[RiskFinding, ...]

    def export_json(self) -> str:
        """Export the risk report as structured JSON.

        Returns:
            JSON representation of this report.
        """
        return self.model_dump_json(indent=2)


@dataclass(frozen=True)
class _NodeClassification:
    """Internal node-to-risk-category classification."""

    category: RiskCategory
    confidence: ConfidenceLevel
    evidence_kind: EvidenceKind
    evidence_detail: str
    assessment: FindingAssessment | None = None


class RiskAnalyzer:
    """Analyze ChokePoint dependency risk from topologies or graphs."""

    CATEGORY_LEVELS: ClassVar[Mapping[RiskCategory, RiskLevel]] = {
        RiskCategory.DNS: RiskLevel.CRITICAL,
        RiskCategory.IDENTITY: RiskLevel.CRITICAL,
        RiskCategory.CDN: RiskLevel.CRITICAL,
        RiskCategory.SECRETS_MANAGER: RiskLevel.CRITICAL,
        RiskCategory.MONITORING: RiskLevel.HIGH,
        RiskCategory.NETWORKING: RiskLevel.HIGH,
        RiskCategory.CI_CD: RiskLevel.MEDIUM,
        RiskCategory.EMAIL: RiskLevel.MEDIUM,
        RiskCategory.SINGLE_SERVICE_ARTICULATION: RiskLevel.LOW,
    }
    BASE_SCORES: ClassVar[Mapping[RiskLevel, int]] = {
        RiskLevel.CRITICAL: 88,
        RiskLevel.HIGH: 70,
        RiskLevel.MEDIUM: 50,
        RiskLevel.LOW: 25,
    }

    def analyze(self, topology: Topology) -> RiskReport:
        """Analyze a topology and produce a structured risk report.

        Args:
            topology: Topology to analyze.

        Returns:
            Risk report.
        """
        graph = GraphBuilder().build(topology)
        return self.analyze_graph(graph)

    def analyze_graph(self, graph: nx.Graph) -> RiskReport:
        """Analyze a NetworkX graph produced from a topology.

        Args:
            graph: NetworkX graph with ChokePoint model attributes.

        Returns:
            Risk report.

        Raises:
            ValueError: If the graph is not a valid ChokePoint graph.
        """
        validation = GraphAnalyzer().validate(graph)
        if not validation.is_valid:
            message = "invalid ChokePoint graph: " + "; ".join(validation.issues)
            raise ValueError(message)

        articulation_points = tuple(sorted(nx.articulation_points(graph)))
        topology = _topology_from_graph(graph)
        dependency_index = _DependencyIndex(topology)
        findings: list[RiskFinding] = []
        emitted_nodes: set[str] = set()

        shared_category_nodes = self._shared_category_nodes(topology, dependency_index)
        for node_id, classifications in shared_category_nodes.items():
            node = topology.nodes[node_id]
            for classification in classifications:
                finding = self._shared_finding(node, classification, dependency_index)
                findings.append(finding)
                emitted_nodes.add(node.id)

        for node_id in articulation_points:
            if node_id in emitted_nodes:
                continue
            node = topology.nodes[node_id]
            impacted_services = dependency_index.impacted_services(node_id)
            if len(impacted_services) == 1:
                findings.append(self._articulation_finding(node, dependency_index))

        ordered_findings = tuple(
            sorted(
                findings,
                key=lambda finding: (
                    -finding.risk_score,
                    finding.risk_level.value,
                    finding.node_id,
                    finding.category.value,
                ),
            )
        )
        report_score = max(
            (finding.risk_score for finding in ordered_findings), default=0
        )
        return RiskReport(
            risk_score=report_score,
            finding_count=len(ordered_findings),
            findings=ordered_findings,
        )

    def _shared_category_nodes(
        self,
        topology: Topology,
        dependency_index: _DependencyIndex,
    ) -> dict[str, tuple[_NodeClassification, ...]]:
        """Return nodes that match shared-risk categories."""
        classified_nodes: dict[str, list[_NodeClassification]] = defaultdict(list)
        for node in topology.nodes.values():
            classifications = _classify_node(node)
            if not classifications:
                continue
            if len(dependency_index.impacted_nodes(node.id)) < MIN_SHARED_DEPENDENTS:
                continue
            for classification in classifications:
                classified_nodes[node.id].append(classification)

        return {
            node_id: tuple(
                sorted(
                    classifications,
                    key=lambda item: (
                        -_confidence_rank(item.confidence),
                        item.category.value,
                    ),
                )
            )
            for node_id, classifications in sorted(classified_nodes.items())
        }

    def _shared_finding(
        self,
        node: Node,
        classification: _NodeClassification,
        dependency_index: _DependencyIndex,
    ) -> RiskFinding:
        """Build a finding for a shared dependency category."""
        category = classification.category
        impacted_nodes = dependency_index.impacted_nodes(node.id)
        impacted_providers = dependency_index.impacted_providers(node.id)
        chains = dependency_index.dependency_chains(node.id)
        assessment = _finding_assessment(classification)
        risk_level = _effective_risk_level(self.CATEGORY_LEVELS[category], assessment)
        score = _risk_score(
            risk_level,
            len(impacted_nodes),
            len(impacted_providers),
            assessment=assessment,
        )
        evidence = _shared_evidence(
            node=node,
            classification=classification,
            dependency_index=dependency_index,
            impacted_nodes=impacted_nodes,
        )

        return RiskFinding(
            node_id=node.id,
            node_name=node.name,
            provider=node.provider,
            category=category,
            risk_level=risk_level,
            criticality=risk_level,
            risk_score=score,
            blast_radius=len(impacted_nodes),
            impacted_nodes=impacted_nodes,
            impacted_providers=impacted_providers,
            dependency_chain=chains,
            confidence=classification.confidence,
            assessment=assessment,
            evidence=evidence,
            explanation=_shared_explanation(
                node,
                category,
                impacted_nodes,
                impacted_providers,
                assessment=assessment,
            ),
        )

    def _articulation_finding(
        self,
        node: Node,
        dependency_index: _DependencyIndex,
    ) -> RiskFinding:
        """Build a low-risk articulation finding."""
        impacted_nodes = dependency_index.impacted_nodes(node.id)
        impacted_providers = dependency_index.impacted_providers(node.id)
        chains = dependency_index.dependency_chains(node.id)
        risk_level = RiskLevel.LOW
        score = _risk_score(
            risk_level,
            len(impacted_nodes),
            len(impacted_providers),
            assessment=FindingAssessment.NEEDS_REVIEW,
        )
        return RiskFinding(
            node_id=node.id,
            node_name=node.name,
            provider=node.provider,
            category=RiskCategory.SINGLE_SERVICE_ARTICULATION,
            risk_level=risk_level,
            criticality=risk_level,
            risk_score=score,
            blast_radius=len(impacted_nodes),
            impacted_nodes=impacted_nodes,
            impacted_providers=impacted_providers,
            dependency_chain=chains,
            confidence=ConfidenceLevel.MEDIUM,
            assessment=FindingAssessment.NEEDS_REVIEW,
            evidence=(
                _node_model_evidence(
                    node,
                    detail=f"{node.name} is present in the analyzed topology.",
                ),
                Evidence(
                    parser="chokepoint.graph",
                    kind=EvidenceKind.GRAPH_ANALYSIS,
                    subject=node.id,
                    detail=(
                        "NetworkX articulation-point analysis identified this "
                        "node on a single service dependency path."
                    ),
                ),
            ),
            explanation=(
                f"{node.name} is an articulation point for a single service path."
            ),
        )


class _DependencyIndex:
    """Dependency traversal helpers for a topology."""

    def __init__(self, topology: Topology) -> None:
        self._topology = topology
        self._incoming: dict[str, list[str]] = defaultdict(list)
        self._outgoing: dict[str, list[str]] = defaultdict(list)
        self._incoming_edges: dict[str, list[Edge]] = defaultdict(list)
        for edge in topology.edges:
            if edge.relationship != Relationship.DEPENDS_ON:
                continue
            self._incoming[edge.target].append(edge.source)
            self._outgoing[edge.source].append(edge.target)
            self._incoming_edges[edge.target].append(edge)

        for values in self._incoming.values():
            values.sort()
        for values in self._outgoing.values():
            values.sort()
        for edge_values in self._incoming_edges.values():
            edge_values.sort(
                key=lambda edge: (edge.source, edge.target, edge.relationship)
            )

    def impacted_nodes(self, node_id: str) -> tuple[str, ...]:
        """Return all nodes that directly or transitively depend on a node."""
        visited: set[str] = set()
        queue: deque[str] = deque(self._incoming[node_id])
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            queue.extend(self._incoming[current])

        return tuple(sorted(visited))

    def impacted_services(self, node_id: str) -> tuple[str, ...]:
        """Return impacted service nodes."""
        return tuple(
            node_id
            for node_id in self.impacted_nodes(node_id)
            if self._topology.nodes[node_id].node_type == NodeType.SERVICE
        )

    def impacted_providers(self, node_id: str) -> tuple[str, ...]:
        """Return impacted providers, excluding the dependency provider."""
        dependency_provider = self._topology.nodes[node_id].provider
        providers = {
            self._topology.nodes[impacted_node].provider
            for impacted_node in self.impacted_nodes(node_id)
            if self._topology.nodes[impacted_node].provider != dependency_provider
        }
        return tuple(sorted(providers))

    def dependency_chains(self, target: str) -> tuple[DependencyChain, ...]:
        """Return shortest dependency chains from impacted nodes to a target."""
        chains: list[DependencyChain] = []
        for source in self.impacted_nodes(target):
            path = self._shortest_dependency_path(source, target)
            if path:
                chains.append(DependencyChain(source=source, target=target, path=path))
        return tuple(sorted(chains, key=lambda chain: (len(chain.path), chain.path)))

    def direct_dependency_edges(self, target: str) -> tuple[Edge, ...]:
        """Return direct `depends_on` edges pointing at a target."""
        return tuple(self._incoming_edges[target])

    def node(self, node_id: str) -> Node:
        """Return a topology node by id."""
        return self._topology.nodes[node_id]

    def _shortest_dependency_path(self, source: str, target: str) -> tuple[str, ...]:
        """Return the shortest source-to-target dependency path."""
        queue: deque[tuple[str, tuple[str, ...]]] = deque([(source, (source,))])
        visited: set[str] = set()
        while queue:
            current, path = queue.popleft()
            if current == target:
                return path
            if current in visited:
                continue
            visited.add(current)
            for next_node in self._outgoing[current]:
                queue.append((next_node, (*path, next_node)))
        return ()


def _topology_from_graph(graph: nx.Graph) -> Topology:
    """Reconstruct a topology from a ChokePoint NetworkX graph."""
    topology = Topology()
    for _, attributes in graph.nodes(data=True):
        node = attributes[GraphBuilder.NODE_ATTR]
        if not isinstance(node, Node):
            raise ValueError("graph contains a node without a ChokePoint Node model")
        topology.add_node(node)

    edge_keys: set[tuple[str, str, Relationship]] = set()
    for _, _, attributes in graph.edges(data=True):
        edges = attributes[GraphBuilder.EDGE_ATTR]
        if not isinstance(edges, tuple):
            raise ValueError("graph contains an edge without ChokePoint Edge models")
        for edge in edges:
            if not isinstance(edge, Edge):
                raise ValueError("graph contains a non-ChokePoint edge model")
            edge_key = (edge.source, edge.target, edge.relationship)
            if edge_key in edge_keys:
                continue
            topology.add_edge(edge)
            edge_keys.add(edge_key)
    return topology


def _classify_node(node: Node) -> tuple[_NodeClassification, ...]:
    """Classify a node into risk categories."""
    text = _classification_text(node)
    classifications: dict[RiskCategory, _NodeClassification] = {}
    _classify_identity_surface(node, text, classifications)
    _classify_external_services(node, text, classifications)
    _classify_network_surface(node, text, classifications)
    _classify_operations(text, classifications, node_id=node.id)

    return tuple(
        sorted(
            classifications.values(),
            key=lambda item: (-_confidence_rank(item.confidence), item.category.value),
        )
    )


def _classification_text(node: Node) -> str:
    """Return normalized node text used by heuristic classifiers."""
    return " ".join(
        (
            node.id,
            node.name,
            node.provider,
            str(node.metadata.get("terraform_type", "")),
            str(node.metadata.get("category", "")),
        )
    ).lower()


def _classify_identity_surface(
    node: Node,
    text: str,
    classifications: dict[RiskCategory, _NodeClassification],
) -> None:
    """Classify DNS, identity, and secrets categories."""
    if node.node_type == NodeType.DNS:
        _add_classification(
            classifications,
            _classification(
                RiskCategory.DNS,
                confidence=ConfidenceLevel.HIGH,
                evidence_kind=EvidenceKind.EXPLICIT_CONFIG,
                evidence_detail=f"{node.id} is explicitly typed as DNS.",
            ),
        )
    elif _contains_any(text, ("dns", "route53")):
        _add_classification(
            classifications,
            _classification(
                RiskCategory.DNS,
                confidence=ConfidenceLevel.MEDIUM,
                evidence_kind=EvidenceKind.HEURISTIC,
                evidence_detail=f"{node.id} matches DNS naming/provider patterns.",
            ),
        )

    if node.node_type == NodeType.IDENTITY:
        _add_classification(
            classifications,
            _classification(
                RiskCategory.IDENTITY,
                confidence=ConfidenceLevel.HIGH,
                evidence_kind=EvidenceKind.EXPLICIT_CONFIG,
                evidence_detail=f"{node.id} is explicitly typed as identity.",
            ),
        )
    elif _contains_any(text, ("iam", "identity", "okta", "auth0", "entra")):
        _add_classification(
            classifications,
            _classification(
                RiskCategory.IDENTITY,
                confidence=ConfidenceLevel.MEDIUM,
                evidence_kind=EvidenceKind.HEURISTIC,
                evidence_detail=(
                    f"{node.id} matches identity naming/provider patterns."
                ),
            ),
        )

    if node.node_type == NodeType.SECRET:
        _add_classification(
            classifications,
            _classification(
                RiskCategory.SECRETS_MANAGER,
                confidence=ConfidenceLevel.HIGH,
                evidence_kind=EvidenceKind.EXPLICIT_CONFIG,
                evidence_detail=f"{node.id} is explicitly typed as secret material.",
            ),
        )
    elif _contains_any(text, ("secret", "secretsmanager", "keyvault", "vault")):
        _add_classification(
            classifications,
            _classification(
                RiskCategory.SECRETS_MANAGER,
                confidence=ConfidenceLevel.MEDIUM,
                evidence_kind=EvidenceKind.HEURISTIC,
                evidence_detail=f"{node.id} matches secrets-manager naming patterns.",
            ),
        )


def _classify_external_services(
    node: Node,
    text: str,
    classifications: dict[RiskCategory, _NodeClassification],
) -> None:
    """Classify CDN and monitoring categories."""
    if _contains_any(text, ("cdn", "cloudfront", "cloudflare", "fastly", "akamai")):
        _add_classification(
            classifications,
            _classification(
                RiskCategory.CDN,
                confidence=ConfidenceLevel.MEDIUM,
                evidence_kind=EvidenceKind.HEURISTIC,
                evidence_detail=f"{node.id} matches CDN naming/provider patterns.",
            ),
        )

    if _contains_any(text, ("monitoring", "datadog", "prometheus", "grafana")):
        _add_classification(
            classifications,
            _classification(
                RiskCategory.MONITORING,
                confidence=ConfidenceLevel.MEDIUM,
                evidence_kind=EvidenceKind.HEURISTIC,
                evidence_detail=(
                    f"{node.id} matches monitoring naming/provider patterns."
                ),
            ),
        )


def _classify_network_surface(
    node: Node,
    text: str,
    classifications: dict[RiskCategory, _NodeClassification],
) -> None:
    """Classify networking while downgrading known topology artifacts."""
    if _is_docker_default_network(node):
        _add_classification(
            classifications,
            _classification(
                RiskCategory.NETWORKING,
                confidence=ConfidenceLevel.LOW,
                evidence_kind=EvidenceKind.HEURISTIC,
                evidence_detail=(
                    f"{node.id} is Docker Compose's default network, which is often "
                    "an automatic local topology artifact."
                ),
                assessment=FindingAssessment.MODELING_ARTIFACT,
            ),
        )
    elif node.node_type == NodeType.NETWORK:
        _add_classification(
            classifications,
            _classification(
                RiskCategory.NETWORKING,
                confidence=ConfidenceLevel.HIGH,
                evidence_kind=EvidenceKind.EXPLICIT_CONFIG,
                evidence_detail=f"{node.id} is explicitly typed as networking.",
            ),
        )
    elif _contains_any(text, ("vpc", "subnet", "network", "gateway", "security_group")):
        _add_classification(
            classifications,
            _classification(
                RiskCategory.NETWORKING,
                confidence=ConfidenceLevel.MEDIUM,
                evidence_kind=EvidenceKind.HEURISTIC,
                evidence_detail=(
                    f"{node.id} matches networking naming/provider patterns."
                ),
            ),
        )


def _classify_operations(
    text: str,
    classifications: dict[RiskCategory, _NodeClassification],
    *,
    node_id: str,
) -> None:
    """Classify operational dependency categories."""
    if _contains_any(
        text,
        (
            "ci/cd",
            "ci-cd",
            "cicd",
            "github-actions",
            "github actions",
            "gitlab-ci",
            "circleci",
            "jenkins",
            "buildkite",
            "azure-pipelines",
        ),
    ):
        _add_classification(
            classifications,
            _classification(
                RiskCategory.CI_CD,
                confidence=ConfidenceLevel.MEDIUM,
                evidence_kind=EvidenceKind.HEURISTIC,
                evidence_detail=f"{node_id} matches CI/CD naming/provider patterns.",
            ),
        )

    if _contains_any(text, ("email", "ses", "sendgrid", "mailgun")):
        _add_classification(
            classifications,
            _classification(
                RiskCategory.EMAIL,
                confidence=ConfidenceLevel.MEDIUM,
                evidence_kind=EvidenceKind.HEURISTIC,
                evidence_detail=f"{node_id} matches email naming/provider patterns.",
            ),
        )


def _risk_score(
    risk_level: RiskLevel,
    blast_radius: int,
    provider_count: int,
    *,
    assessment: FindingAssessment,
) -> int:
    """Calculate a bounded risk score."""
    base = RiskAnalyzer.BASE_SCORES[risk_level]
    score = base + min(blast_radius * 3, 9) + min(provider_count * 2, 6)
    if assessment == FindingAssessment.MODELING_ARTIFACT:
        return min(score, 20)
    return min(score, 100)


def _shared_explanation(
    node: Node,
    category: RiskCategory,
    impacted_nodes: tuple[str, ...],
    impacted_providers: tuple[str, ...],
    *,
    assessment: FindingAssessment,
) -> str:
    """Generate human-readable explanation text for a shared finding."""
    if assessment == FindingAssessment.MODELING_ARTIFACT:
        return (
            f"{node.name} looks like a shared {category.value.replace('_', ' ')} "
            "dependency, but ChokePoint classified it as a modeling artifact. "
            "Review the source topology before treating it as a production risk."
        )

    label = category.value.replace("_", " ").upper()
    if impacted_providers:
        providers = _human_join(
            tuple(provider.upper() for provider in impacted_providers)
        )
        return (
            f"{node.name} {label} is a shared dependency across {providers}, "
            f"with a blast radius of {len(impacted_nodes)} node(s)."
        )
    return f"{node.name} {label} is shared by {len(impacted_nodes)} dependent node(s)."


def _classification(
    category: RiskCategory,
    *,
    confidence: ConfidenceLevel,
    evidence_kind: EvidenceKind,
    evidence_detail: str,
    assessment: FindingAssessment | None = None,
) -> _NodeClassification:
    """Create a node classification."""
    return _NodeClassification(
        category=category,
        confidence=confidence,
        evidence_kind=evidence_kind,
        evidence_detail=evidence_detail,
        assessment=assessment,
    )


def _add_classification(
    classifications: dict[RiskCategory, _NodeClassification],
    candidate: _NodeClassification,
) -> None:
    """Add the highest-confidence classification for a category."""
    existing = classifications.get(candidate.category)
    if existing is None or _confidence_rank(candidate.confidence) > _confidence_rank(
        existing.confidence
    ):
        classifications[candidate.category] = candidate


def _finding_assessment(classification: _NodeClassification) -> FindingAssessment:
    """Return the review assessment for a classification-backed finding."""
    if classification.assessment is not None:
        return classification.assessment
    if classification.confidence == ConfidenceLevel.HIGH:
        return FindingAssessment.CONFIRMED
    if classification.confidence == ConfidenceLevel.MEDIUM:
        return FindingAssessment.LIKELY
    return FindingAssessment.NEEDS_REVIEW


def _effective_risk_level(
    category_level: RiskLevel,
    assessment: FindingAssessment,
) -> RiskLevel:
    """Return the displayed risk level after trust calibration."""
    if assessment == FindingAssessment.MODELING_ARTIFACT:
        return RiskLevel.LOW
    return category_level


def _shared_evidence(
    *,
    node: Node,
    classification: _NodeClassification,
    dependency_index: _DependencyIndex,
    impacted_nodes: tuple[str, ...],
) -> tuple[Evidence, ...]:
    """Build evidence entries for a shared dependency finding."""
    direct_edges = dependency_index.direct_dependency_edges(node.id)
    evidence: list[Evidence] = [
        _node_model_evidence(
            node,
            kind=classification.evidence_kind,
            detail=classification.evidence_detail,
        )
    ]

    for edge in direct_edges[:MAX_EDGE_EVIDENCE]:
        evidence.append(
            _edge_model_evidence(
                edge,
                source_node=dependency_index.node(edge.source),
                target_node=node,
            )
        )

    omitted_count = len(direct_edges) - MAX_EDGE_EVIDENCE
    if omitted_count > 0:
        evidence.append(
            Evidence(
                parser="chokepoint.report",
                kind=EvidenceKind.GRAPH_ANALYSIS,
                subject=node.id,
                detail=(
                    f"{omitted_count} additional direct dependency edge(s) were "
                    "summarized to keep the finding compact."
                ),
            )
        )

    evidence.append(
        Evidence(
            parser="chokepoint.graph",
            kind=EvidenceKind.GRAPH_ANALYSIS,
            subject=node.id,
            detail=(
                f"Dependency traversal found {len(impacted_nodes)} direct or "
                "transitive node(s) depending on this node."
            ),
        )
    )
    return tuple(evidence)


def _node_model_evidence(
    node: Node,
    *,
    kind: EvidenceKind = EvidenceKind.EXPLICIT_CONFIG,
    detail: str,
) -> Evidence:
    """Build evidence from a node model."""
    return Evidence(
        parser=_parser_from_metadata(node.metadata),
        source=_source_from_metadata(node.metadata),
        line=_line_from_metadata(node.metadata),
        kind=kind,
        subject=node.id,
        detail=detail,
    )


def _edge_model_evidence(
    edge: Edge,
    *,
    source_node: Node,
    target_node: Node,
) -> Evidence:
    """Build evidence from an edge model."""
    parser = _parser_from_metadata(edge.metadata)
    source = (
        _source_from_metadata(edge.metadata)
        or _source_from_metadata(source_node.metadata)
        or _source_from_metadata(target_node.metadata)
    )
    kind = (
        EvidenceKind.INFERRED
        if str(edge.metadata.get("source", "")).lower() == "inference"
        else EvidenceKind.EXPLICIT_CONFIG
    )
    return Evidence(
        parser=parser,
        source=source,
        line=_line_from_metadata(edge.metadata),
        kind=kind,
        subject=f"{edge.source}->{edge.target}",
        detail=(
            f"{edge.source} declares `{edge.relationship.value}` on {edge.target}."
        ),
    )


def _parser_from_metadata(metadata: Metadata) -> str:
    """Infer the parser that produced a node or edge."""
    platform = metadata.get("platform")
    if isinstance(platform, str) and platform:
        return platform

    source = metadata.get("source")
    if isinstance(source, str) and source in {
        "cloudformation",
        "docker-compose",
        "inference",
        "kubernetes",
        "pulumi",
        "terraform",
    }:
        return source

    if "terraform_type" in metadata:
        return "terraform"
    if "cloudformation_type" in metadata:
        return "cloudformation"
    if "pulumi_type" in metadata:
        return "pulumi"
    return "manual"


def _source_from_metadata(metadata: Metadata) -> str | None:
    """Return source file metadata when it is available."""
    for key in ("source_file", "source_path", "source"):
        value = metadata.get(key)
        if isinstance(value, str) and value and not _looks_like_parser_label(value):
            return value
    return None


def _line_from_metadata(metadata: Metadata) -> int | None:
    """Return a one-based source line number when available."""
    for key in ("line", "source_line"):
        value = metadata.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return None


def _looks_like_parser_label(value: str) -> bool:
    """Return whether a string is a parser label rather than a source path."""
    return value in {
        "advanced",
        "cloudformation",
        "docker-compose",
        "inference",
        "kubernetes",
        "manual",
        "pulumi",
        "terraform",
    }


def _is_docker_default_network(node: Node) -> bool:
    """Return whether a node is Docker Compose's implicit default network."""
    platform = node.metadata.get("platform")
    return (
        node.node_type == NodeType.NETWORK
        and platform == "docker-compose"
        and (node.name == "default" or node.id.endswith(":default"))
    )


def _confidence_rank(confidence: ConfidenceLevel) -> int:
    """Return sort rank for confidence."""
    return {
        ConfidenceLevel.HIGH: 3,
        ConfidenceLevel.MEDIUM: 2,
        ConfidenceLevel.LOW: 1,
    }[confidence]


def _human_join(values: tuple[str, ...]) -> str:
    """Join values for human-readable explanation text."""
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == HUMAN_JOIN_PAIR_COUNT:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    """Return whether any needle appears in text."""
    return any(needle in text for needle in needles)
