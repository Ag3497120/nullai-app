import os
import argparse
import json
import asyncio

from iath_decoder import IathDecoder
from iath_encoder import IathEncoder
from domain_manager import DomainManager # DomainManagerをインポート

def consolidate_tiles(input_dir: str, output_file: str, domain_id: str):
    """
    指定されたディレクトリ内のタイルファイルを読み込み、指定されたドメインの
    マスター.iathデータベースファイルに統合します。
    """
    print(f"--- データベース統合開始 (ドメイン: {domain_id}) ---")
    print(f"入力ディレクトリ: {input_dir}")
    print(f"出力ファイル: {output_file}")

    # ドメインスキーマからドメインコードを取得
    domain_manager = DomainManager()
    schema = domain_manager.get_schema(domain_id)
    if not schema:
        print(f"エラー: ドメイン '{domain_id}' のスキーマが domain_schemas.json に見つかりません。")
        return
    domain_code = int(schema.get("domain_code", "0x0"), 16) # 16進数文字列を整数に変換

    if not os.path.isdir(input_dir):
        print(f"エラー: 入力ディレクトリ '{input_dir}' が存在しません。")
        return

    tile_files = [f for f in os.listdir(input_dir) if f.endswith('.iath')]
    if not tile_files:
        print(f"エラー: 入力ディレクトリ '{input_dir}' に.iathファイルが見つかりません。")
        return
        
    print(f"{len(tile_files)}個のタイルファイルを検出しました。")

    all_tiles = []
    decoder = IathDecoder()

    print("\nステップ1: 個別タイルのデコード中...")
    for filename in tile_files:
        filepath = os.path.join(input_dir, filename)
        try:
            with open(filepath, 'rb') as f:
                compressed_data = f.read()
            tile_dict = decoder.decode_tile(compressed_data)
            if tile_dict:
                all_tiles.append(tile_dict)
        except Exception as e:
            print(f"警告: ファイル '{filename}' のデコードに失敗しました。スキップします。エラー: {e}")
    
    print(f"  -> {len(all_tiles)}件のタイルを正常にデコードしました。")

    if not all_tiles:
        print("エラー: デコードできるタイルがありませんでした。処理を中断します。")
        return

    print("\nステップ2: マスターDBファイルのバッチエンコード中...")
    encoder = IathEncoder()
    # ドメインコードを渡すように変更
    master_db_content = encoder.encode_batch(all_tiles, domain_code=domain_code)

    try:
        with open(output_file, 'wb') as f:
            f.write(master_db_content)
        print(f"\n✓ 成功: 統合データベースを {output_file} ({len(master_db_content)} bytes) に保存しました。")
    except IOError as e:
        print(f"\n✗ 失敗: ファイルの書き込みに失敗しました - {e}")
    
    print("--- データベース統合完了 ---")

def main():
    parser = argparse.ArgumentParser(description="Ilm-Athens データベース管理ツール")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_consolidate = subparsers.add_parser(
        "consolidate",
        help="個別の.iathタイルファイルを単一のマスターDBファイルに統合します。"
    )
    parser_consolidate.add_argument(
        "--input-dir",
        default="generated_tiles",
        help="入力ディレクトリ (デフォルト: generated_tiles)"
    )
    parser_consolidate.add_argument(
        "--output-file",
        default="ilm_athens_db.iath",
        help="出力ファイル名 (デフォルト: ilm_athens_db.iath)"
    )
    parser_consolidate.add_argument(
        "--domain",
        default="medical",
        required=True, # ドメイン指定を必須にする
        help="対象とする知識ドメイン (例: medical, legal)"
    )

    args = parser.parse_args()

    if args.command == "consolidate":
        consolidate_tiles(args.input_dir, args.output_file, args.domain)

if __name__ == "__main__":
    main()
