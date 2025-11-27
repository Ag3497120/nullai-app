from collections import OrderedDict

class LRUCache:
    """
    Least Recently Used (LRU) Cache.
    設計書で言及されているホットキャッシュのシンプルな実装です。
    """
    
    def __init__(self, max_size: int = 20):
        """
        Args:
            max_size (int): キャッシュの最大サイズ。
        """
        if max_size <= 0:
            raise ValueError("max_size must be a positive integer.")
        self.max_size = max_size
        self._cache = OrderedDict()

    def __contains__(self, key):
        "'key in cache' 構文をサポートします。" 
        return key in self._cache

    def __getitem__(self, key):
        "キーに対応する値を取得し、そのキーを最も最近使用されたものとしてマークします。" 
        if key not in self._cache:
            raise KeyError(f"Key '{key}' not found in cache.")
        
        # アイテムを最後に移動させて「最近使用した」ことを示す
        self._cache.move_to_end(key)
        return self._cache[key]

    def __setitem__(self, key, value):
        "キーと値のペアをキャッシュに追加します。" 
        if key in self._cache:
            # 既存のキーの場合は、最近使用したことを示すために移動
            self._cache.move_to_end(key)
        
        self._cache[key] = value
        
        # キャッシュサイズが上限を超えた場合、最も古く使用されていないアイテムを削除
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    def get(self, key, default=None):
        "キーが存在しない場合に例外を送出しないバージョンの get です。" 
        if key in self._cache:
            return self[key]
        return default

    @property
    def size(self):
        "現在のキャッシュサイズを返します。" 
        return len(self._cache)

# --- 使用例 ---
if __name__ == "__main__":
    # サイズ3のキャッシュを作成
    cache = LRUCache(max_size=3)
    
    print("--- Cache Operations ---")
    cache['coord_1'] = "Tile 1 Data"
    cache['coord_2'] = "Tile 2 Data"
    cache['coord_3'] = "Tile 3 Data"
    print("Cache after adding 3 items:", cache._cache)
    
    # coord_1にアクセス -> 最近使用されたアイテムになる
    print("\nAccessing 'coord_1'...")
    _ = cache['coord_1']
    print("Cache state:", cache._cache)

    # 新しいアイテムを追加 -> 最も古く使用されていない 'coord_2' が削除される
    print("\nAdding 'coord_4', expecting 'coord_2' to be evicted...")
    cache['coord_4'] = "Tile 4 Data"
    print("Cache state:", cache._cache)

    print("\nIs 'coord_2' in cache?", 'coord_2' in cache)
    print("Is 'coord_3' in cache?", 'coord_3' in cache)
    print("Current cache size:", cache.size)
