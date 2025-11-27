import os
from typing import Optional, List, Dict, Tuple
import asyncio
from pathlib import Path

# 既存のIathDecoderをインポート
# プロジェクトルートにiath_decoder.pyがあることを想定
from iath_decoder import IathDecoder


class IathDBInterface:
    """
    .iathファイルを使用するDBインターフェース
    """
    
    def __init__(self, db_file_path: str):
        """
        Args:
            db_file_path: .iathファイルのパス
                例: "cardiology_prototype_v1.iath"
        """
        self.db_file_path = db_file_path
        self.decoder = IathDecoder()
        self.loaded_tiles: Dict[str, Dict] = {}
        self.index: Dict[Tuple[int, int, int], str] = {}  # 座標→タイルIDマップ
        self.is_loaded = False
    
    def load_db(self) -> bool:
        """
        DBファイル全体をメモリに読み込む
        
        Returns:
            bool: ロード成功したか
        """
        try:
            if not os.path.exists(self.db_file_path):
                print(f"❌ DBファイルが見つかりません: {self.db_file_path}")
                return False
            
            with open(self.db_file_path, 'rb') as f:
                db_content = f.read()
            
            # 複数タイルをデコードする decode_batch を使用
            tiles = self.decoder.decode_batch(db_content)
            
            self.loaded_tiles = tiles
            
            # インデックスを構築
            for tile_id, tile in tiles.items():
                # ドメインスキーマに応じて空間名が変わることを想定
                coord = tile.get("coordinates", {}).get("medical_space") 
                if coord:
                    rounded_coord = (
                        int(round(coord[0])),
                        int(round(coord[1])),
                        int(round(coord[2]))
                    )
                    self.index[rounded_coord] = tile_id
            
            self.is_loaded = True
            print(f"✓ ロード完了: {len(tiles)}件のタイル")
            return True
        
        except Exception as e:
            print(f"❌ DBロード失敗: {e}")
            return False
    
    async def fetch_async(
        self,
        coordinate: Tuple[float, float, float],
        tolerance: float = 10.0
    ) -> Optional[Dict]:
        """
        座標から該当タイルを非同期取得
        
        Args:
            coordinate: (x, y, z) 座標
            tolerance: 座標の許容誤差（デフォルト10）
        
        Returns:
            マッチしたタイル、またはNone
        """
        if not self.is_loaded:
            # DBがロードされていない場合、先にロードを試みる
            print("⚠️ DBがロードされていません。ロードを試みます...")
            if not self.load_db():
                return None
        
        # ブロッキング検索を別スレッドで実行
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._search_coordinate,
            coordinate,
            tolerance
        )
    
    def _search_coordinate(
        self,
        coordinate: Tuple[float, float, float],
        tolerance: float
    ) -> Optional[Dict]:
        """座標検索（同期版）"""
        x, y, z = coordinate
        
        for tile in self.loaded_tiles.values():
            # NOTE: ここで "medical_space" にハードコードされている点を修正する必要がある
            # ドメインスキーマから適切な空間名を取得するべき
            domain_space = tile.get("coordinates", {}).get("medical_space")
            if not domain_space:
                continue
            
            distance = self._euclidean_distance(
                (x, y, z),
                domain_space
            )
            
            if distance <= tolerance:
                return tile
        
        return None
    
    @staticmethod
    def _euclidean_distance(
        coord1: Tuple[float, float, float],
        coord2: Tuple[float, float, float]
    ) -> float:
        """ユークリッド距離を計算"""
        return sum((c1 - c2)**2 for c1, c2 in zip(coord1, coord2))**0.5
    
    def search_by_keyword(self, keyword: str) -> List[Dict]:
        """
        キーワードでタイルを検索
        """
        results = []
        
        for tile in self.loaded_tiles.values():
            content = tile.get("content", {}).get("final_response", "")
            if keyword.lower() in content.lower():
                results.append(tile)
        
        return results
    
    def get_tile_by_id(self, tile_id: str) -> Optional[Dict]:
        """タイルIDで直接取得"""
        return self.loaded_tiles.get(tile_id)
    
    def list_all_tiles(self) -> List[Dict]:
        """全タイルを一覧"""
        return list(self.loaded_tiles.values())
    
    def get_stats(self) -> Dict:
        """DB統計情報"""
        if not self.is_loaded:
            return {"status": "not_loaded"}
        
        certainties = []
        for tile in self.loaded_tiles.values():
            c = tile.get("coordinates", {}).get("meta_space", [0])[0]
            certainties.append(c)
        
        return {
            "status": "loaded",
            "total_tiles": len(self.loaded_tiles),
            "avg_certainty": sum(certainties) / len(certainties) if certainties else 0,
            "min_certainty": min(certainties) if certainties else 0,
            "max_certainty": max(certainties) if certainties else 0,
            "file_size_mb": os.path.getsize(self.db_file_path) / (1024**2)
        }


# テスト用ヘルパー
class IathDBTestHelper:
    """DB接続テスト用ユーティリティ"""
    
    @staticmethod
    async def test_basic_loading(db_file_path: str):
        """基本的なロードテスト"""
        db = IathDBInterface(db_file_path)
        
        print(f"\n【テスト】DB基本ロード")
        print(f"ファイル: {db_file_path}")
        
        success = db.load_db()
        
        if success:
            stats = db.get_stats()
            print(f"✓ ロード成功")
            print(f"  タイル数: {stats['total_tiles']}")
            print(f"  平均確実性: {stats['avg_certainty']:.1f}%")
        else:
            print(f"✗ ロード失敗")
        
        return success
    
    @staticmethod
    async def test_coordinate_search(db_file_path: str):
        """座標検索テスト"""
        db = IathDBInterface(db_file_path)
        db.load_db()
        
        test_coords = [
            (28, 35, 15),   # 心筋梗塞の診断
            (42, 50, 40),   # 肺関連
        ]
        
        print(f"\n【テスト】座標検索")
        
        for coord in test_coords:
            tile = await db.fetch_async(coord, tolerance=15)
            
            if tile:
                print(f"✓ 座標{coord}: 見つかった")
                print(f"  トピック: {tile.get('metadata', {}).get('topic', 'N/A')}")
            else:
                print(f"✗ 座標{coord}: 見つからない")
        
        return True


# 使用例
if __name__ == "__main__":
    import asyncio
    
    # --- 注意 ---
    # このテストを実行する前に、まず create_tile_from_topic.py を実行して
    # `cardiology_prototype_v1.iath` ファイルを作成しておく必要があります。
    # `python create_tile_from_topic.py cardiology_prototype_v1` のように実行し、
    # そのファイル名を `db_file` 変数に指定してください。
    # ----------
    
    db_file = "cardiology_prototype_v1.iath" # サンプルDBファイル名
    
    print("="*60)
    print("Ilm-Athens DB接続テスト")
    print("="*60)
    
    async def main():
        helper = IathDBTestHelper()
        
        # テスト1: ロード
        if await helper.test_basic_loading(db_file):
            print("\n✓ テスト1パス")
        
        # テスト2: 座標検索
        if await helper.test_coordinate_search(db_file):
            print("\n✓ テスト2パス")
        
        print("\n" + "="*60)
        print("全テストPASS ✓")
        print("="*60)
    
    asyncio.run(main())
