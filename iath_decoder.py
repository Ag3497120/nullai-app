import struct
import zstandard as zstd
import json
from typing import Dict # これを追加
 # これを追加
from datetime import datetime

class IathDecoder:
    """
    .iath互換の圧縮バイナリデータをKnowledge Tileオブジェクトにデコードします。
    """

    def _decode_string_from_buffer(self, buffer, offset):
        """バッファからNULL終端文字列をデコードします。"""
        end_offset = buffer.find(b'\0', offset)
        if end_offset == -1:
            raise ValueError("Invalid string format in buffer")
        s = buffer[offset:end_offset].decode('utf-8')
        return s, end_offset + 1

    def _decode_metadata(self, buffer: bytes) -> dict:
        """メタデータセクションをデコードします。"""
        offset = 0
        kid, offset = self._decode_string_from_buffer(buffer, offset)
        topic, offset = self._decode_string_from_buffer(buffer, offset)
        created_at = buffer[offset:offset+27].decode('ascii').rstrip('\0')
        
        return {"knowledge_id": kid, "topic": topic, "created_at": created_at}

    def _decode_coordinates(self, buffer: bytes) -> dict:
        """座標セクションをデコードします。"""
        coords = struct.unpack("<ffffff", buffer)
        return {
            "medical_space": (coords[0], coords[1], coords[2]),
            "meta_space": (coords[3], coords[4], coords[5])
        }

    def _decode_content(self, buffer: bytes) -> dict:
        """コンテンツセクションをデコードします。"""
        offset = 0
        
        # thinking_process
        think_len = struct.unpack("<I", buffer[offset:offset+4])[0]
        offset += 4
        thinking = buffer[offset:offset+think_len].decode('utf-8')
        offset += think_len
        
        # final_response
        resp_len = struct.unpack("<I", buffer[offset:offset+4])[0]
        offset += 4
        response = buffer[offset:offset+resp_len].decode('utf-8')
        
        return {"thinking_process": thinking, "final_response": response}

    def _decode_verification(self, buffer: bytes) -> dict:
        """検証履歴セクションをデコードします。"""
        status_map = {
            0: "pending_review", 1: "partial_verified", 
            2: "verified", 3: "expert_confirmed"
        }
        
        status_code, initial_certainty, reviewer_count = struct.unpack("<BBI", buffer[:6])
        status = status_map.get(status_code, "unknown")
        
        # NOTE: レビュアーIDのデコードはエンコーダーに合わせて省略
        
        return {
            "status": status,
            "initial_certainty": initial_certainty,
            "reviewers": [] # ダミー
        }

    def decode_tile(self, compressed_binary: bytes) -> dict:
        """
        単一の圧縮タイルデータをデコードしてKnowledge Tileオブジェクトを復元します。
        
        Args:
            compressed_binary (bytes): 圧縮されたバイナリデータ。

        Returns:
            dict: 復元されたKnowledge Tileオブジェクト。
        """
        try:
            dctx = zstd.ZstdDecompressor()
            uncompressed = dctx.decompress(compressed_binary)
        except zstd.ZstdError as e:
            raise ValueError(f"Zstandard decompression failed: {e}")

        offset = 0
        decoded_sections = {}

        try:
            # Metadata
            md_len = struct.unpack("<I", uncompressed[offset:offset+4])[0]
            offset += 4
            decoded_sections["metadata"] = self._decode_metadata(uncompressed[offset:offset+md_len])
            offset += md_len

            # Coordinates
            coord_len = struct.unpack("<I", uncompressed[offset:offset+4])[0]
            offset += 4
            decoded_sections["coordinates"] = self._decode_coordinates(uncompressed[offset:offset+coord_len])
            offset += coord_len

            # Content
            content_len = struct.unpack("<I", uncompressed[offset:offset+4])[0]
            offset += 4
            decoded_sections["content"] = self._decode_content(uncompressed[offset:offset+content_len])
            offset += content_len

            # Verification
            verif_len = struct.unpack("<I", uncompressed[offset:offset+4])[0]
            offset += 4
            decoded_sections["verification"] = self._decode_verification(uncompressed[offset:offset+verif_len])
            offset += verif_len

        except (struct.error, IndexError, UnicodeDecodeError) as e:
            raise ValueError(f"Failed to parse tile structure at offset {offset}: {e}")

        # スキーマに準拠するよう、デコードしたセクションを再構成
        restored_tile = {
            "metadata": decoded_sections.get("metadata"),
            "content": decoded_sections.get("content"),
            "coordinates": decoded_sections.get("coordinates", {}),
            "verification": decoded_sections.get("verification"),
            # 以下はエンコードしていないためデフォルト値
            "source": {},
            "history": []
        }
        # 不足しているキーを補完
        if "coordinates" in restored_tile:
            restored_tile["coordinates"].setdefault("reasoning_path", [])

        return restored_tile

    def decode_batch(self, full_db_content: bytes) -> Dict[str, Dict]:
        """
        ヘッダー、インデックス、データセクションを含む完全な.iath DBファイルをデコードします。
        
        Args:
            full_db_content (bytes): .iathファイル全体のバイナリコンテンツ。

        Returns:
            Dict[str, Dict]: tile_idをキーとする、デコードされた知識タイルの辞書。
        """
        print("--- .iathデータベースのバッチデコード開始 ---")
        # 1. ヘッダーをパース
        if len(full_db_content) < 64:
            raise ValueError("Invalid .iath file: Header is too short.")
        
        magic, version, domain_code, compression_type, checksum, index_offset, data_offset = \
            struct.unpack("<4sIBB32sQQ6x", full_db_content[:64])

        if magic != b'ILMA':
            raise ValueError("Invalid .iath file: Magic number is incorrect.")
        
        print(f"  - Header OK: Version={version}, Domain={domain_code}, Index Offset={index_offset}, Data Offset={data_offset}")

        # 2. インデックスセクションを読み込み
        # データオフセットの開始位置までがインデックスセクション
        index_data_binary = full_db_content[index_offset:data_offset]
        index = json.loads(index_data_binary.decode('utf-8'))
        print(f"  - インデックス読み込み完了: {len(index)}件")

        # 3. データセクションから各タイルをデコード
        all_tiles = {}
        for item in index:
            tile_id, offset, length = item['id'], item['offset'], item['length']
            
            # データセクション内でのタイルの範囲を特定
            start = data_offset + offset
            end = start + length
            tile_compressed_data = full_db_content[start:end]
            
            # 個別のタイルをデコード
            try:
                decoded_tile = self.decode_tile(tile_compressed_data)
                # デコード結果にIDを付与（JSONにはIDがないため）
                if "metadata" in decoded_tile and "knowledge_id" not in decoded_tile["metadata"]:
                     decoded_tile["metadata"]["knowledge_id"] = tile_id
                all_tiles[tile_id] = decoded_tile
            except Exception as e:
                print(f"警告: タイルID {tile_id} のデコードに失敗しました。スキップします。エラー: {e}")

        print(f"  - 全タイルのデコード完了: {len(all_tiles)}件")
        print("--- バッチデコード完了 ---")
        return all_tiles

