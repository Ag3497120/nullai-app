from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from enum import Enum
import numpy as np
from datetime import datetime, timedelta, UTC

# --- ヘルパークラスとEnum ---

@dataclass
class CylindricalCoordinate:
    """円柱座標系 (Z: 時間, R: 重要度, Theta: トピック)"""
    z: float  # 時間軸 (経過時間やタイムスタンプ)
    r: float  # 半径 (重要度やアクセス頻度)
    theta: float  # 角度 (0-2π, 医学領域などのトピック)

class MemoryLayer(Enum):
    """記憶の層（年輪）"""
    FORMATION = "形成層"  # 最も新しい、ワーキングメモリ
    CRUST = "外層"       # 最近の記憶
    WOOD = "木部"        # 圧縮された長期記憶
    CORE = "中核"        # 抽象化された原則

@dataclass
class DendriticMemoryNode:
    """樹木型記憶空間の各ノード"""
    node_id: str
    content: str
    coordinate: CylindricalCoordinate
    layer: MemoryLayer = MemoryLayer.FORMATION
    importance: float = 0.5
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(UTC))
    access_count: int = 0
    is_compressed: bool = False

    def age_days(self) -> float:
        return (datetime.now(UTC) - self.created_at).total_seconds() / 86400

# --- メインクラス ---

class DendriticMemorySpace:
    """
    知識を樹木型の3D空間に配置・管理する。

    機能:
    - IathDBとの統合によるタイル一括読み込み
    - ドメイン対応の座標変換
    - 階層的記憶圧縮（年輪化）
    - 関連記憶の検索
    """
    def __init__(self, max_nodes: int = 100000, db_interface=None):
        self.nodes: Dict[str, DendriticMemoryNode] = {}
        self.max_nodes = max_nodes
        self.db_interface = db_interface
        self.domain_space_names = {
            "medical": "medical_space",
            "legal": "legal_space",
            "economics": "economics_space"
        }
        self._is_synced = False

    def set_db_interface(self, db_interface):
        """IathDBインターフェースを設定"""
        self.db_interface = db_interface
        self._is_synced = False

    async def sync_from_db(self, domain: str = "medical") -> int:
        """
        IathDBから全タイルを読み込み、樹木型記憶空間に統合する。

        Args:
            domain: ドメイン名（medical/legal/economics）

        Returns:
            統合されたタイル数
        """
        if not self.db_interface:
            print("警告: DBインターフェースが設定されていません。")
            return 0

        if not self.db_interface.is_loaded:
            print("  -> DBをロード中...")
            if not self.db_interface.load_db():
                return 0

        tiles = self.db_interface.list_all_tiles()
        print(f"  -> {len(tiles)}件のタイルを樹木型記憶空間に統合中...")

        integrated_count = 0
        for tile in tiles:
            try:
                self.integrate_tile(tile, domain)
                integrated_count += 1
            except Exception as e:
                print(f"警告: タイル統合エラー: {e}")

        self._is_synced = True
        print(f"  -> {integrated_count}件のタイルを統合完了")
        return integrated_count

    def get_stats(self) -> Dict:
        """記憶空間の統計情報を取得"""
        layer_counts = {}
        for layer in MemoryLayer:
            layer_counts[layer.value] = sum(
                1 for n in self.nodes.values() if n.layer == layer
            )

        avg_importance = 0.0
        if self.nodes:
            avg_importance = sum(n.importance for n in self.nodes.values()) / len(self.nodes)

        return {
            "total_nodes": len(self.nodes),
            "max_nodes": self.max_nodes,
            "utilization": len(self.nodes) / self.max_nodes,
            "layer_distribution": layer_counts,
            "avg_importance": avg_importance,
            "is_synced_with_db": self._is_synced
        }

    def _cartesian_to_cylindrical(self, cartesian_coord: Tuple[float, float, float]) -> CylindricalCoordinate:
        """従来のXYZ座標を、新しい樹木型円柱座標に変換する"""
        x, y, z_time = cartesian_coord
        
        # X,Y平面を、トピック(角度theta)と重要度(半径r)にマッピング
        theta = np.arctan2(y, x)  # -πからπの範囲
        if theta < 0:
            theta += 2 * np.pi # 0から2πの範囲に正規化
            
        r = np.sqrt(x**2 + y**2)
        
        # Z軸はそのまま時間(z)として使用
        return CylindricalCoordinate(z=z_time, r=r, theta=theta)

    def integrate_tile(self, tile: Dict, domain: str = "medical"):
        """
        IathDBから読み込んだ知識タイルを、樹木型記憶空間に統合する。

        Args:
            tile: 知識タイル辞書
            domain: ドメイン名（座標空間の選択に使用）
        """
        # タイルIDを取得（複数の場所をチェック）
        tile_id = (
            tile.get("metadata", {}).get("knowledge_id") or
            tile.get("metadata", {}).get("tile_id") or
            tile.get("tile_id") or
            f"tile_{hash(str(tile))}"
        )

        # ドメイン対応の空間名を取得
        space_name = self.domain_space_names.get(domain, "medical_space")

        # 座標を取得（複数の場所をチェック）
        cartesian_coord = (
            tile.get("coordinates", {}).get(space_name) or
            tile.get("coordinates", {}).get("medical_space") or  # フォールバック
            tile.get("coordinate")
        )

        if not cartesian_coord:
            # 座標がない場合はスキップ（エラーではなく警告）
            return

        # 円柱座標に変換
        cylindrical_coord = self._cartesian_to_cylindrical(tuple(cartesian_coord))

        # コンテンツを取得（複数の場所をチェック）
        content = (
            tile.get("content", {}).get("final_response", "") or
            tile.get("content", {}).get("data", "") or
            tile.get("content", "") if isinstance(tile.get("content"), str) else ""
        )

        # 重要度（確実性）を取得
        meta_space = tile.get("coordinates", {}).get("meta_space", [50, 0, 0])
        importance = meta_space[0] / 100 if meta_space else 0.5

        # ノード数上限チェック
        if len(self.nodes) >= self.max_nodes:
            self._evict_least_important()

        # 樹木型記憶ノードを作成
        node = DendriticMemoryNode(
            node_id=tile_id,
            content=content,
            coordinate=cylindrical_coord,
            layer=MemoryLayer.CRUST,  # DBからのタイルは「外層」に配置
            importance=importance
        )
        self.nodes[node.node_id] = node

    def _evict_least_important(self):
        """最も重要度の低いノードを削除（容量管理）"""
        if not self.nodes:
            return

        # 重要度が最低のノードを特定
        least_important = min(self.nodes.values(), key=lambda n: n.importance)
        del self.nodes[least_important.node_id]

    def _angle_distance(self, angle1: float, angle2: float) -> float:
        """2つの角度の最短距離を計算 (0-2πの範囲)"""
        diff = abs(angle1 - angle2)
        return min(diff, 2 * np.pi - diff)

    async def retrieve_memories(
        self,
        query_theta: float,
        radius_range: Tuple[float, float] = (0, 100),
        max_results: int = 5
    ) -> List[DendriticMemoryNode]:
        """トピック角度（theta）で関連する記憶を検索する"""
        results = []
        for node in self.nodes.values():
            if radius_range[0] <= node.coordinate.r <= radius_range[1]:
                # 角度の近さ、重要度、最近アクセスされたかを考慮したスコア
                angle_dist = self._angle_distance(query_theta, node.coordinate.theta)
                relevance_score = (1 - angle_dist / np.pi) + node.importance + (1 / (node.age_days() + 1))
                results.append((node, relevance_score))

        results.sort(key=lambda x: x[1], reverse=True)

        # アクセスカウントを更新
        retrieved_nodes = []
        for node, score in results[:max_results]:
            node.access_count += 1
            node.last_accessed = datetime.now(UTC)
            retrieved_nodes.append(node)

        return retrieved_nodes

    async def retrieve_by_coordinate(
        self,
        coordinate: Tuple[float, float, float],
        tolerance: float = 15.0,
        max_results: int = 5
    ) -> List[DendriticMemoryNode]:
        """
        デカルト座標（XYZ）で関連する記憶を検索する。
        IathDBの座標系と互換性あり。

        Args:
            coordinate: (x, y, z) 座標
            tolerance: 許容距離
            max_results: 最大結果数

        Returns:
            関連する記憶ノードのリスト
        """
        query_cyl = self._cartesian_to_cylindrical(coordinate)
        x, y, z = coordinate

        results = []
        for node in self.nodes.values():
            # 円柱座標での距離計算
            angle_dist = self._angle_distance(query_cyl.theta, node.coordinate.theta)
            r_dist = abs(query_cyl.r - node.coordinate.r)
            z_dist = abs(query_cyl.z - node.coordinate.z)

            # 複合距離（重み付け）
            distance = np.sqrt(
                (angle_dist * 50)**2 +  # 角度は距離に変換
                r_dist**2 +
                z_dist**2
            )

            if distance <= tolerance:
                # スコア計算（距離が近いほど高スコア）
                score = (tolerance - distance) / tolerance + node.importance
                results.append((node, score, distance))

        # スコア順にソート
        results.sort(key=lambda x: x[1], reverse=True)

        # アクセスカウントを更新
        retrieved_nodes = []
        for node, score, dist in results[:max_results]:
            node.access_count += 1
            node.last_accessed = datetime.now(UTC)
            retrieved_nodes.append(node)

        return retrieved_nodes

    async def search_by_content(self, keyword: str, max_results: int = 10) -> List[DendriticMemoryNode]:
        """キーワードで記憶を検索"""
        results = []

        for node in self.nodes.values():
            if keyword.lower() in node.content.lower():
                results.append((node, node.importance))

        results.sort(key=lambda x: x[1], reverse=True)
        return [node for node, _ in results[:max_results]]

    async def compress_old_memories(self, days_threshold: int = 30):
        """年輪化: 古い記憶を圧縮し、内層へ移動させる（プレースホルダー）"""
        print(f"\nCompressing memories older than {days_threshold} days...")
        compressed_count = 0
        for node in self.nodes.values():
            if node.age_days() >= days_threshold and not node.is_compressed:
                # 実際の圧縮処理はここに実装
                node.is_compressed = True
                node.layer = MemoryLayer.WOOD
                compressed_count += 1
        print(f"  -> {compressed_count} nodes were moved to the 'WOOD' layer.")

# --- 使用例 ---
async def main():
    # 1. 記憶空間を初期化
    memory_space = DendriticMemorySpace()

    # 2. ダミーの知識タイルを作成
    mock_tile_1 = {
        "metadata": {"knowledge_id": "ami_diag_001"},
        "content": {"final_response": "急性心筋梗塞は心電図とトロポニンで診断します..."},
        "coordinates": {"medical_space": [28, 45, 15], "meta_space": [95, 150, 85]}
    }
    mock_tile_2 = {
        "metadata": {"knowledge_id": "copd_treat_002"},
        "content": {"final_response": "COPDの治療には気管支拡張薬が用いられます..."},
        "coordinates": {"medical_space": [40, 30, 70], "meta_space": [90, 180, 88]}
    }

    # 3. タイルを記憶空間に統合
    memory_space.integrate_tile(mock_tile_1)
    memory_space.integrate_tile(mock_tile_2)

    # 4. 検索クエリをシミュレート
    # 心臓病学に近いトピック (x=28, y=45 -> theta ≈ 0.98)
    query_topic_theta = np.arctan2(45, 28)
    
    retrieved = await memory_space.retrieve_memories(query_topic_theta)
    
    for node in retrieved:
        print(f"    - Found Node: {node.node_id}, Content: '{node.content[:20]}...' ")

    # 5. 圧縮をシミュレート
    # 1つ目のノードの作成日を古くして圧縮対象にする
    memory_space.nodes["ami_diag_001"].created_at = datetime.utcnow() - timedelta(days=31)
    await memory_space.compress_old_memories()
    print(f"  -> Node 'ami_diag_001' new layer: {memory_space.nodes['ami_diag_001'].layer}")


if __name__ == "__main__":
    asyncio.run(main())
