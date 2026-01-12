"""
Semantic Clustering 레이어

키워드 매칭 대신 "의미적 유사성"으로 이벤트 그룹화
- 임베딩 기반: 문서를 벡터로 변환
- 점진적 클러스터링: 새 문서 → 기존 클러스터 or 새 클러스터
- 새 클러스터 감지: 기존에 없던 주제 출현 = 새로운 사건

장점:
- 키워드 없이도 관련 문서 그룹화
- 완전히 새로운 유형의 사건 감지
- 연구 결과: LLM 임베딩이 키워드 기반보다 클러스터링 품질 우수
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SemanticCluster:
    """의미적 클러스터"""
    cluster_id: str
    centroid: np.ndarray              # 클러스터 중심 벡터
    documents: list[dict]             # 클러스터에 속한 문서들
    created_at: datetime
    last_updated: datetime
    keywords: list[str] = field(default_factory=list)  # 대표 키워드 (LLM 생성)

    @property
    def size(self) -> int:
        return len(self.documents)

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "size": self.size,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "keywords": self.keywords,
            "sample_titles": [d.get("title", "")[:100] for d in self.documents[:3]],
        }


@dataclass
class ClusteringSignal:
    """클러스터링 기반 신호"""
    signal_type: str              # new_cluster, cluster_growth, cluster_merge
    cluster: SemanticCluster
    severity: float               # 0.0 ~ 1.0
    description: str
    detected_at: datetime
    metadata: dict = field(default_factory=dict)


class SemanticClusterer:
    """
    실시간 의미적 클러스터링

    점진적 클러스터링 (Incremental Clustering):
    - 새 문서가 들어오면 기존 클러스터와 유사도 계산
    - 유사도 높으면 → 기존 클러스터에 추가
    - 유사도 낮으면 → 새 클러스터 생성 (= 새로운 주제!)
    """

    def __init__(
        self,
        similarity_threshold: float = 0.7,     # 클러스터 소속 임계값
        new_cluster_threshold: float = 0.4,    # 새 클러스터 생성 임계값
        min_cluster_size: int = 2,             # 최소 클러스터 크기
        max_clusters: int = 100,               # 최대 클러스터 수
        cluster_ttl_hours: int = 24,           # 클러스터 유효 시간
        embedding_dim: int = 1024,             # 임베딩 차원 (BGE-M3 기준)
    ):
        self.similarity_threshold = similarity_threshold
        self.new_cluster_threshold = new_cluster_threshold
        self.min_cluster_size = min_cluster_size
        self.max_clusters = max_clusters
        self.cluster_ttl_hours = cluster_ttl_hours
        self.embedding_dim = embedding_dim

        self.clusters: dict[str, SemanticCluster] = {}
        self.embedder = None  # Lazy loading

    async def initialize(self) -> bool:
        """임베딩 모델 초기화"""
        try:
            from sentence_transformers import SentenceTransformer

            # BGE-M3: 다국어, 고성능, 1024차원
            logger.info("Loading embedding model (BAAI/bge-m3)...")
            self.embedder = SentenceTransformer("BAAI/bge-m3")
            logger.info("Embedding model loaded successfully")
            return True

        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            return False
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            return False

    def _embed(self, texts: list[str]) -> np.ndarray:
        """텍스트를 임베딩 벡터로 변환"""
        if self.embedder is None:
            raise RuntimeError("Embedder not initialized. Call initialize() first.")
        return self.embedder.encode(texts, normalize_embeddings=True)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """코사인 유사도 계산 (정규화된 벡터라면 내적)"""
        return float(np.dot(a, b))

    def _generate_cluster_id(self, text: str) -> str:
        """클러스터 ID 생성"""
        return hashlib.md5(f"{text}:{datetime.utcnow().timestamp()}".encode()).hexdigest()[:12]

    async def process_documents(
        self,
        documents: list[dict],
        text_field: str = "title",
    ) -> list[ClusteringSignal]:
        """
        문서들을 클러스터링하고 신호 반환

        Args:
            documents: 문서 목록 [{"title": "...", "url": "...", ...}]
            text_field: 임베딩에 사용할 텍스트 필드

        Returns:
            감지된 클러스터링 신호 목록
        """
        if not documents:
            return []

        if self.embedder is None:
            logger.warning("Embedder not initialized, skipping clustering")
            return []

        now = datetime.utcnow()
        signals = []

        # 1. 오래된 클러스터 정리
        self._cleanup_old_clusters(now)

        # 2. 문서 임베딩
        texts = [doc.get(text_field, "") for doc in documents]
        texts = [t if t else "empty" for t in texts]  # 빈 문자열 처리

        try:
            embeddings = self._embed(texts)
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return []

        # 3. 각 문서를 클러스터에 할당
        new_clusters_created = []

        for doc, embedding in zip(documents, embeddings):
            result = self._assign_to_cluster(doc, embedding, now)

            if result["action"] == "new_cluster":
                new_clusters_created.append(result["cluster"])
            elif result["action"] == "cluster_growth":
                # 클러스터 급성장 체크
                cluster = result["cluster"]
                if cluster.size >= 5 and cluster.size % 5 == 0:  # 5의 배수마다 체크
                    signals.append(ClusteringSignal(
                        signal_type="cluster_growth",
                        cluster=cluster,
                        severity=min(1.0, cluster.size / 20),
                        description=f"Cluster '{cluster.cluster_id}' grew to {cluster.size} documents",
                        detected_at=now,
                        metadata={"growth_rate": cluster.size},
                    ))

        # 4. 새 클러스터 신호 생성
        for cluster in new_clusters_created:
            if cluster.size >= self.min_cluster_size:
                signals.append(ClusteringSignal(
                    signal_type="new_cluster",
                    cluster=cluster,
                    severity=0.8,
                    description=f"New topic cluster emerged with {cluster.size} documents",
                    detected_at=now,
                    metadata={"initial_size": cluster.size},
                ))
                logger.info(f"New cluster detected: {cluster.cluster_id} ({cluster.size} docs)")

        return signals

    def _assign_to_cluster(
        self,
        doc: dict,
        embedding: np.ndarray,
        timestamp: datetime,
    ) -> dict:
        """
        문서를 적절한 클러스터에 할당

        Returns:
            {"action": "existing"|"new_cluster"|"cluster_growth", "cluster": SemanticCluster}
        """
        # 기존 클러스터와 유사도 계산
        best_cluster = None
        best_similarity = 0.0

        for cluster in self.clusters.values():
            similarity = self._cosine_similarity(embedding, cluster.centroid)
            if similarity > best_similarity:
                best_similarity = similarity
                best_cluster = cluster

        # 케이스 1: 기존 클러스터에 속함
        if best_similarity >= self.similarity_threshold and best_cluster:
            best_cluster.documents.append(doc)
            best_cluster.last_updated = timestamp
            # 중심 업데이트 (이동 평균)
            n = len(best_cluster.documents)
            best_cluster.centroid = (
                (n - 1) / n * best_cluster.centroid + 1 / n * embedding
            )
            return {"action": "cluster_growth", "cluster": best_cluster}

        # 케이스 2: 새 클러스터 생성
        if best_similarity < self.new_cluster_threshold or not best_cluster:
            cluster_id = self._generate_cluster_id(doc.get("title", ""))
            new_cluster = SemanticCluster(
                cluster_id=cluster_id,
                centroid=embedding,
                documents=[doc],
                created_at=timestamp,
                last_updated=timestamp,
            )

            # 클러스터 수 제한
            if len(self.clusters) >= self.max_clusters:
                self._remove_smallest_cluster()

            self.clusters[cluster_id] = new_cluster
            return {"action": "new_cluster", "cluster": new_cluster}

        # 케이스 3: 애매한 경우 - 가장 가까운 클러스터에 추가
        if best_cluster:
            best_cluster.documents.append(doc)
            best_cluster.last_updated = timestamp
            return {"action": "existing", "cluster": best_cluster}

        # 예외 케이스
        return {"action": "none", "cluster": None}

    def _cleanup_old_clusters(self, now: datetime):
        """오래된 클러스터 정리"""
        cutoff = now - timedelta(hours=self.cluster_ttl_hours)
        expired = [
            cid for cid, c in self.clusters.items()
            if c.last_updated < cutoff
        ]
        for cid in expired:
            del self.clusters[cid]
            logger.debug(f"Removed expired cluster: {cid}")

    def _remove_smallest_cluster(self):
        """가장 작은 클러스터 제거"""
        if not self.clusters:
            return
        smallest = min(self.clusters.values(), key=lambda c: c.size)
        del self.clusters[smallest.cluster_id]
        logger.debug(f"Removed smallest cluster: {smallest.cluster_id}")

    def find_similar_clusters(
        self,
        text: str,
        top_k: int = 3,
    ) -> list[tuple[SemanticCluster, float]]:
        """
        텍스트와 유사한 클러스터 찾기

        Args:
            text: 검색 텍스트
            top_k: 반환할 클러스터 수

        Returns:
            [(클러스터, 유사도), ...] 유사도 내림차순
        """
        if self.embedder is None or not self.clusters:
            return []

        embedding = self._embed([text])[0]

        similarities = [
            (cluster, self._cosine_similarity(embedding, cluster.centroid))
            for cluster in self.clusters.values()
        ]

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def get_active_clusters(
        self,
        min_size: int = 2,
        hours: int = 6,
    ) -> list[SemanticCluster]:
        """
        최근 활성화된 클러스터 반환

        Args:
            min_size: 최소 클러스터 크기
            hours: 최근 N시간 이내

        Returns:
            활성 클러스터 목록 (크기 내림차순)
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        active = [
            c for c in self.clusters.values()
            if c.size >= min_size and c.last_updated >= cutoff
        ]
        return sorted(active, key=lambda c: c.size, reverse=True)

    def get_status(self) -> dict:
        """현재 상태 반환"""
        return {
            "total_clusters": len(self.clusters),
            "total_documents": sum(c.size for c in self.clusters.values()),
            "largest_cluster": max((c.size for c in self.clusters.values()), default=0),
            "embedder_loaded": self.embedder is not None,
        }

    def reset(self):
        """클러스터 초기화"""
        self.clusters.clear()


async def test_semantic_clustering():
    """테스트: Semantic Clustering"""
    print("\n" + "=" * 60)
    print("SEMANTIC CLUSTERING TEST")
    print("=" * 60)

    clusterer = SemanticClusterer(
        similarity_threshold=0.7,
        new_cluster_threshold=0.4,
    )

    # 초기화
    print("\nInitializing embedder...")
    success = await clusterer.initialize()
    if not success:
        print("Failed to initialize embedder")
        return

    # 테스트 문서
    documents = [
        # 클러스터 1: 우크라이나 전쟁
        {"title": "Russian forces advance in eastern Ukraine", "url": "1"},
        {"title": "Ukraine military reports heavy fighting near Bakhmut", "url": "2"},
        {"title": "NATO discusses additional support for Kyiv", "url": "3"},

        # 클러스터 2: 이란 시위
        {"title": "Protests erupt in Tehran over economic conditions", "url": "4"},
        {"title": "Iranian security forces clash with demonstrators", "url": "5"},

        # 클러스터 3: 완전히 다른 주제
        {"title": "Apple announces new iPhone release date", "url": "6"},
    ]

    print(f"\nProcessing {len(documents)} documents...")
    signals = await clusterer.process_documents(documents)

    print(f"\nSignals detected: {len(signals)}")
    for signal in signals:
        print(f"  - {signal.signal_type}: {signal.description}")

    print(f"\nActive clusters:")
    for cluster in clusterer.get_active_clusters(min_size=1):
        print(f"  - {cluster.cluster_id}: {cluster.size} docs")
        for doc in cluster.documents[:2]:
            print(f"      • {doc['title'][:50]}...")

    print(f"\nStatus: {clusterer.get_status()}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_semantic_clustering())
