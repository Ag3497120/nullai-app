import asyncio
import os
import argparse

# リファクタリングされたタイル生成関数をインポート
from create_tile_from_topic import create_knowledge_tile_pipeline

async def batch_create_tiles(topics_file: str, output_dir: str, domain: str):
    """
    トピックリストを読み込み、指定されたドメインの知識タイルをバッチ処理で生成します。
    """
    print(f"--- バッチ処理開始 ---")
    print(f"  トピックファイル: {topics_file}")
    print(f"  出力ディレクトリ: {output_dir}")
    print(f"  対象ドメイン: {domain}")
    
    # 出力先ディレクトリがなければ作成
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"出力先ディレクトリを作成しました: {output_dir}")

    try:
        with open(topics_file, 'r', encoding='utf-8') as f:
            topics = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"エラー: トピックファイル '{topics_file}' が見つかりません。")
        return

    print(f"{len(topics)}件のトピックを処理します。")
    
    created_files = []
    for i, topic in enumerate(topics):
        print(f"\n({i+1}/{len(topics)}) 処理中: {topic}")
        
        safe_filename = topic.replace(" ", "_").replace("/", "_").replace("（", "").replace("）", "")[:30]
        output_path = os.path.join(output_dir, f"{safe_filename}.iath")

        generated_file = await create_knowledge_tile_pipeline(
            topic=topic,
            domain_id=domain, # ドメインを指定
            output_filename=output_path,
            save_json=False 
        )
        
        if generated_file:
            created_files.append(generated_file)

    print("\n--- バッチ処理完了 ---")
    print(f"{len(created_files)}件の.iathファイルを {output_dir} に生成しました。")

def main():
    parser = argparse.ArgumentParser(description="Ilm-Athens 知識タイルバッチ生成ツール")
    parser.add_argument(
        "--topics-file",
        default="topics.txt",
        help="トピックをリストしたテキストファイル (デフォルト: topics.txt)"
    )
    parser.add_argument(
        "--output-dir",
        default="generated_tiles",
        help="生成された.iathファイルを保存するディレクトリ (デフォルト: generated_tiles)"
    )
    parser.add_argument(
        "--domain",
        default="medical",
        help="対象とする知識ドメイン (例: medical, legal) (デフォルト: medical)"
    )
    args = parser.parse_args()

    asyncio.run(batch_create_tiles(args.topics_file, args.output_dir, args.domain))

if __name__ == "__main__":
    main()
