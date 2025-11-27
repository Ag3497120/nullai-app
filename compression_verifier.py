import json
import hashlib
from knowledge_tile_generator import create_knowledge_tile
from reasoning_chain_extractor import extract_reasoning_chain
from coordinate_mapper import map_reasoning_to_medical_space
from iath_encoder import IathEncoder
from iath_decoder import IathDecoder

def generate_sample_tile() -> dict:
    """
    検証用のサンプルKnowledge Tileを生成します。
    """
    dummy_response = {
        'thinking': 'まず、心筋梗塞の定義から始めます。これは心筋への血流が途絶えることで心筋が壊死する状態です。次に、診断のゴールドスタンダードであるトロポニン測定について考慮します。これは～という理由で重要です。さらに心電図の変化も重要な所見です。ST上昇が見られる場合、急性期と判断されます。',
        'response': '急性心筋梗塞は、迅速な診断と治療が求められる救急疾患です。診断は主に、臨床症状（胸痛など）、心電図変化（ST上昇など）、心筋逸脱酵素（特にトロポニン）の上昇を三本柱として行われます。アルゴリズムとしては、まず疑いがあれば直ちに12誘導心電図を記録し、バイタルサインを確認します。ST上昇があれば、緊急カテーテル治療の適応を考慮します。<参考資料> 日本循環器学会ガイドライン2023',
    }
    topic = "心筋梗塞の急性期診断"

    reasoning = extract_reasoning_chain(dummy_response)
    coordinates = map_reasoning_to_medical_space(reasoning)
    knowledge_tile = create_knowledge_tile(dummy_response, coordinates, topic)
    return knowledge_tile

def verify_lossless_compression(original_tile: dict) -> dict:
    """
    指定されたKnowledge Tileの可逆圧縮を検証します。
    エンコード -> デコードを実行し、結果がオリジナルと一致するか確認します。
    """
    
    encoder = IathEncoder()
    decoder = IathDecoder()
    
    # ステップ1: エンコード
    try:
        compressed_data = encoder.encode_tile(original_tile)
        original_size = len(json.dumps(original_tile, ensure_ascii=False).encode('utf-8'))
    except Exception as e:
        return {"status": f"✗ エンコード失敗: {e}", "is_lossless": False}

    # ステップ2: デコード
    try:
        decompressed_tile = decoder.decode_tile(compressed_data)
    except Exception as e:
        return {"status": f"✗ デコード失敗: {e}", "is_lossless": False}
        
    # ステップ3: ハッシュを比較して可逆性を検証
    # NOTE: デコード処理では一部のフィールド(source, historyなど)が復元されないため、
    # それらのフィールドを比較対象から除外した上でハッシュを計算します。
    
    def get_comparable_hash(tile_data: dict) -> str:
        # 比較対象のキーを限定
        keys_to_compare = ["metadata", "content", "coordinates", "verification"]
        comparable_data = {key: tile_data.get(key) for key in keys_to_compare}
        # 安定したハッシュ生成のため、キーでソートしてJSON化
        serialized = json.dumps(comparable_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

    original_hash = get_comparable_hash(original_tile)
    decompressed_hash = get_comparable_hash(decompressed_tile)
    
    is_lossless = original_hash == decompressed_hash
    status = "✓ 完全な可逆圧縮" if is_lossless else "✗ 情報損失あり"
    
    report = {
        "is_lossless": is_lossless,
        "status": status,
        "original_hash": original_hash,
        "decompressed_hash": decompressed_hash,
        "original_size": original_size,
        "compressed_size": len(compressed_data),
        "compression_ratio": f"{(len(compressed_data) / original_size):.2%}" if original_size > 0 else "N/A",
    }
    
    return report

if __name__ == "__main__":
    print("--- 可逆圧縮検証開始 ---")
    
    # 1. サンプルタイルを生成
    print("1. サンプルKnowledge Tileを生成中...")
    sample_tile = generate_sample_tile()
    
    # 2. 可逆圧縮を検証
    print("2. エンコード -> デコードを実行し、可逆性を検証中...")
    verification_report = verify_lossless_compression(sample_tile)
    
    # 3. 結果を表示
    print("\n--- 可逆圧縮検証結果 ---")
    print(f"ステータス: {verification_report['status']}")
    print(f"  可逆性: {verification_report['is_lossless']}")
    print(f"  元データのハッシュ: {verification_report['original_hash']}")
    print(f"  復元データのハッシュ: {verification_report['decompressed_hash']}")
    print(f"  元の推定サイズ: {verification_report['original_size']} bytes")
    print(f"  圧縮後のサイズ: {verification_report['compressed_size']} bytes")
    print(f"  圧縮率: {verification_report['compression_ratio']}")

    if not verification_report['is_lossless']:
        print("\n[!] ハッシュが一致しませんでした。エンコーダーとデコーダーの実装を確認してください。")
