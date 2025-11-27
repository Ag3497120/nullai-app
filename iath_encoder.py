import struct
import zstandard as zstd
from datetime import datetime
import json # これを追加

class IathEncoder:
    """
    Knowledge Tileオブジェクトを.iath互換の圧縮バイナリにエンコードします。
    """
    
    def _encode_reviewer_reference(self, reviewer: dict) -> bytes:
        """
        レビュアー情報をエンコードします。
        当面はダミー実装とし、レビュアーIDを固定長で返します。
        将来的にはVerifier Dictionaryを参照するインデックスを返す必要があります。
        """
        reviewer_id = reviewer.get("reviewer_id", "unknown").encode('utf-8')
        return struct.pack("<36s", reviewer_id[:36]) # UUID string length

    def _encode_string(self, s: str) -> bytes:
        """NULL終端のUTF-8文字列をエンコードします。"""
        return s.encode('utf-8') + b'\0'

    def _encode_metadata(self, metadata: dict) -> bytes:
        """メタデータをバイナリ化します。"""
        kid = self._encode_string(metadata["knowledge_id"])
        topic = self._encode_string(metadata["topic"])
        created_at_iso = metadata.get("created_at", datetime.now().isoformat())
        created_at = created_at_iso.encode('ascii')[:27] # ISO format with Z
        return kid + topic + created_at

    def _encode_coordinates(self, coordinates: dict) -> bytes:
        """座標をバイナリ化（6つの浮動小数点数）。"""
        medical_space = coordinates["medical_space"]
        meta_space = coordinates["meta_space"]
        
        return struct.pack(
            "<ffffff",
            float(medical_space[0]), float(medical_space[1]), float(medical_space[2]),
            float(meta_space[0]), float(meta_space[1]), float(meta_space[2])
        )

    def _encode_content(self, content: dict) -> bytes:
        """コンテンツ（テキスト）をバイナリ化します。"""
        thinking = content["thinking_process"].encode('utf-8')
        response = content["final_response"].encode('utf-8')
        
        # 各パートの長さを前に付けて連結
        result = struct.pack("<I", len(thinking)) + thinking
        result += struct.pack("<I", len(response)) + response
        return result

    def _encode_verification(self, verification: dict) -> bytes:
        """検証履歴をバイナリ化します。"""
        status_map = {
            "pending_review": 0, "partial_verified": 1, 
            "verified": 2, "expert_confirmed": 3
        }
        status_code = status_map.get(verification.get("status", "pending_review"), 0)
        
        initial_certainty = int(verification.get("initial_certainty", 0))
        reviewer_count = len(verification.get("reviewers", []))
        
        result = struct.pack("<BBI", status_code, initial_certainty, reviewer_count)
        
        for reviewer in verification.get("reviewers", []):
            result += self._encode_reviewer_reference(reviewer)
            
        return result

    def encode_tile(self, tile: dict) -> bytes:
        """
        単一のKnowledge Tileをエンコードし、zstdで圧縮します。
        
        Args:
            tile (dict): Knowledge Tileオブジェクト。

        Returns:
            bytes: 圧縮されたバイナリデータ。
        """
        # 各セクションをエンコード
        metadata_bin = self._encode_metadata(tile["metadata"])
        coord_bin = self._encode_coordinates(tile["coordinates"])
        content_bin = self._encode_content(tile["content"])
        verification_bin = self._encode_verification(tile["verification"])
        
        # NOTE: reasoning_path, source, historyなどは今回省略し、主要な部分のみ実装
        
        # 長さプレフィックスを付けて連結
        uncompressed = b"".join([
            struct.pack("<I", len(metadata_bin)), metadata_bin,
            struct.pack("<I", len(coord_bin)), coord_bin,
            struct.pack("<I", len(content_bin)), content_bin,
            struct.pack("<I", len(verification_bin)), verification_bin,
        ])
        
        # zstdで圧縮
        cctx = zstd.ZstdCompressor(level=19)
        compressed = cctx.compress(uncompressed)
        
        return compressed
        
    def encode_batch(self, tiles: List[Dict], domain_code: int = 1) -> bytes:
        """
        複数の知識タイルを受け取り、完全な.iathデータベースファイルのバイナリを生成します。

        Args:
            tiles (List[Dict]): エンコードする知識タイルの辞書のリスト。
            domain_code (int): ヘッダーに書き込むドメインコード (1: medical, 2: legal, etc.)。

        Returns:
            bytes: 完全な.iathファイルのバイナリコンテンツ。
        """
        print(f"--- {len(tiles)}件のタイルのバッチエンコード開始 (ドメインコード: {domain_code}) ---")
        
        index = []
        data_chunks = []
        current_offset = 0

        # 1. 各タイルを個別にエンコードし、データチャンクとインデックスを作成
        for tile in tiles:
            tile_id = tile.get("metadata", {}).get("knowledge_id")
            if not tile_id:
                print("警告: knowledge_idのないタイルをスキップします。")
                continue

            compressed_data = self.encode_tile(tile)
            data_length = len(compressed_data)
            
            index.append({"id": tile_id, "offset": current_offset, "length": data_length})
            data_chunks.append(compressed_data)
            
            current_offset += data_length
        
        print("  - 全タイルの個別エンコード完了。")

        # 2. インデックスセクションをシリアライズ
        index_binary = json.dumps(index, ensure_ascii=False).encode('utf-8')
        print(f"  - インデックス作成完了 (サイズ: {len(index_binary)} bytes)")

        # 3. データセクションを結合
        data_section = b"".join(data_chunks)

        # 4. ヘッダーを作成
        header_size = 64
        index_offset = header_size
        data_offset = index_offset + len(index_binary)
        
        checksum = b'\0' * 32

        header = struct.pack(
            "<4sIBB32sQQ6x",
            b'ILMA',      # Magic number
            1,           # Version
            domain_code, # ドメインコードを引数から設定
            1,           # Compression Type (0x01=zstd)
            checksum,
            index_offset,
            data_offset
        )
        print("  - ヘッダー作成完了。")
        
        # 5. すべてのセクションを結合
        full_db_content = header + index_binary + data_section
        print("--- バッチエンコード完了 ---")
        
        return full_db_content

