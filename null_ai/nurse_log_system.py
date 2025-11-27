"""
NullAI 倒木システム (NurseLog System)

森林の倒木が次世代の栄養となるように、
古いモデルの知識を新モデルに継承する世代交代システム。

機能:
1. 推論履歴からトレーニングデータを抽出
2. 複数フォーマットでエクスポート (JSONL, CSV, Parquet, HuggingFace Datasets)
3. 新モデルのファインチューニング
4. DB保管システムとの連携
"""
import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)

ExportFormat = Literal["jsonl", "csv", "parquet", "hf_dataset"]


class InferenceHistory:
    """推論履歴の管理"""

    def __init__(self, storage_path: str = "inference_history"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save_inference(
        self,
        question: str,
        response: str,
        domain_id: str,
        model_name: str,
        confidence: float,
        thinking_process: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """推論結果を保存"""
        inference_id = hashlib.sha256(
            f"{question}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        record = {
            "inference_id": inference_id,
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "response": response,
            "domain_id": domain_id,
            "model_name": model_name,
            "confidence": confidence,
            "thinking_process": thinking_process,
            "metadata": metadata or {}
        }

        # 日付ごとにファイル分割
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = self.storage_path / f"history_{date_str}.jsonl"

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        logger.info(f"Saved inference {inference_id} to {file_path}")
        return inference_id

    def load_history(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        domain_id: Optional[str] = None,
        min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        """推論履歴を読み込み"""
        history = []

        for file_path in sorted(self.storage_path.glob("history_*.jsonl")):
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)

                        # フィルタリング
                        if domain_id and record.get("domain_id") != domain_id:
                            continue
                        if record.get("confidence", 0) < min_confidence:
                            continue
                        if start_date and record.get("timestamp", "") < start_date:
                            continue
                        if end_date and record.get("timestamp", "") > end_date:
                            continue

                        history.append(record)

        return history


class TrainingDataExporter:
    """トレーニングデータのエクスポート"""

    def __init__(self, output_dir: str = "training_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_jsonl(
        self,
        history: List[Dict[str, Any]],
        output_file: str,
        format_type: Literal["chat", "instruction", "completion"] = "chat"
    ) -> str:
        """JSONL形式でエクスポート"""
        output_path = self.output_dir / output_file

        with open(output_path, "w", encoding="utf-8") as f:
            for record in history:
                if format_type == "chat":
                    # ChatML形式
                    item = {
                        "messages": [
                            {"role": "system", "content": f"You are an expert in {record['domain_id']}."},
                            {"role": "user", "content": record["question"]},
                            {"role": "assistant", "content": record["response"]}
                        ]
                    }
                elif format_type == "instruction":
                    # Instruction形式
                    item = {
                        "instruction": record["question"],
                        "output": record["response"],
                        "input": "",
                        "domain": record["domain_id"]
                    }
                else:  # completion
                    # Completion形式
                    item = {
                        "prompt": record["question"],
                        "completion": record["response"]
                    }

                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        logger.info(f"Exported {len(history)} records to {output_path} ({format_type} format)")
        return str(output_path)

    def export_csv(
        self,
        history: List[Dict[str, Any]],
        output_file: str
    ) -> str:
        """CSV形式でエクスポート"""
        import csv

        output_path = self.output_dir / output_file

        with open(output_path, "w", encoding="utf-8", newline="") as f:
            if not history:
                return str(output_path)

            fieldnames = ["question", "response", "domain_id", "model_name", "confidence", "timestamp"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for record in history:
                writer.writerow({
                    "question": record["question"],
                    "response": record["response"],
                    "domain_id": record["domain_id"],
                    "model_name": record["model_name"],
                    "confidence": record["confidence"],
                    "timestamp": record["timestamp"]
                })

        logger.info(f"Exported {len(history)} records to {output_path} (CSV format)")
        return str(output_path)

    def export_parquet(
        self,
        history: List[Dict[str, Any]],
        output_file: str
    ) -> str:
        """Parquet形式でエクスポート"""
        try:
            import pandas as pd
            import pyarrow.parquet as pq

            output_path = self.output_dir / output_file

            df = pd.DataFrame([
                {
                    "question": r["question"],
                    "response": r["response"],
                    "domain_id": r["domain_id"],
                    "model_name": r["model_name"],
                    "confidence": r["confidence"],
                    "timestamp": r["timestamp"]
                }
                for r in history
            ])

            df.to_parquet(output_path, engine="pyarrow", compression="snappy")

            logger.info(f"Exported {len(history)} records to {output_path} (Parquet format)")
            return str(output_path)

        except ImportError:
            logger.error("pandas and pyarrow are required for Parquet export. Install with: pip install pandas pyarrow")
            raise

    def export_hf_dataset(
        self,
        history: List[Dict[str, Any]],
        dataset_name: str,
        push_to_hub: bool = False,
        hub_repo: Optional[str] = None
    ) -> str:
        """HuggingFace Dataset形式でエクスポート"""
        try:
            from datasets import Dataset

            data = {
                "question": [r["question"] for r in history],
                "response": [r["response"] for r in history],
                "domain_id": [r["domain_id"] for r in history],
                "confidence": [r["confidence"] for r in history]
            }

            dataset = Dataset.from_dict(data)

            # ローカル保存
            output_path = self.output_dir / dataset_name
            dataset.save_to_disk(str(output_path))

            logger.info(f"Exported {len(history)} records to {output_path} (HF Dataset format)")

            # HuggingFace Hubにプッシュ
            if push_to_hub and hub_repo:
                dataset.push_to_hub(hub_repo)
                logger.info(f"Pushed dataset to HuggingFace Hub: {hub_repo}")

            return str(output_path)

        except ImportError:
            logger.error("datasets library is required for HF Dataset export. Install with: pip install datasets")
            raise


class ModelSuccessionManager:
    """モデル世代交代マネージャー"""

    def __init__(
        self,
        history_manager: InferenceHistory,
        exporter: TrainingDataExporter,
        succession_threshold: int = 1000
    ):
        self.history_manager = history_manager
        self.exporter = exporter
        self.succession_threshold = succession_threshold
        self.succession_log_path = Path("succession_log.json")

    def check_succession_trigger(self) -> bool:
        """世代交代のトリガーをチェック"""
        history = self.history_manager.load_history()

        # 高品質な推論が閾値を超えたら世代交代
        high_quality = [r for r in history if r.get("confidence", 0) >= 0.8]

        return len(high_quality) >= self.succession_threshold

    async def prepare_succession(
        self,
        domain_id: Optional[str] = None,
        min_confidence: float = 0.8
    ) -> Dict[str, Any]:
        """世代交代の準備"""
        logger.info(f"Preparing succession for domain: {domain_id or 'all'}")

        # 高品質な推論履歴を取得
        history = self.history_manager.load_history(
            domain_id=domain_id,
            min_confidence=min_confidence
        )

        if len(history) < 100:
            logger.warning(f"Not enough high-quality inferences: {len(history)}")
            return {"status": "insufficient_data", "count": len(history)}

        # 複数フォーマットでエクスポート
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exports = {}

        # JSONL (ChatML形式)
        jsonl_file = f"training_data_{timestamp}.jsonl"
        exports["jsonl"] = self.exporter.export_jsonl(
            history, jsonl_file, format_type="chat"
        )

        # CSV
        csv_file = f"training_data_{timestamp}.csv"
        exports["csv"] = self.exporter.export_csv(history, csv_file)

        # Parquetとデータセット（オプショナル）
        try:
            parquet_file = f"training_data_{timestamp}.parquet"
            exports["parquet"] = self.exporter.export_parquet(history, parquet_file)
        except ImportError:
            logger.info("Skipping Parquet export (pandas not installed)")

        try:
            dataset_name = f"dataset_{timestamp}"
            exports["hf_dataset"] = self.exporter.export_hf_dataset(
                history, dataset_name
            )
        except ImportError:
            logger.info("Skipping HF Dataset export (datasets not installed)")

        # 世代交代ログを保存
        succession_log = {
            "timestamp": datetime.now().isoformat(),
            "domain_id": domain_id,
            "records_count": len(history),
            "min_confidence": min_confidence,
            "exports": exports
        }

        self._append_succession_log(succession_log)

        logger.info(f"Succession preparation complete: {len(history)} records exported")

        return {
            "status": "prepared",
            "count": len(history),
            "exports": exports,
            "log": succession_log
        }

    def _append_succession_log(self, log_entry: Dict[str, Any]):
        """世代交代ログを追記"""
        logs = []
        if self.succession_log_path.exists():
            with open(self.succession_log_path, "r", encoding="utf-8") as f:
                logs = json.load(f)

        logs.append(log_entry)

        with open(self.succession_log_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)

    def get_succession_history(self) -> List[Dict[str, Any]]:
        """世代交代履歴を取得"""
        if not self.succession_log_path.exists():
            return []

        with open(self.succession_log_path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def create_standalone_package(
        self,
        domain_id: Optional[str] = None,
        min_confidence: float = 0.8,
        db_path: Optional[str] = None,
        output_dir: str = "succession_packages"
    ) -> Dict[str, Any]:
        """
        完全なスタンドアロンパッケージを作成

        含まれるもの:
        - トレーニングデータ (全フォーマット)
        - Knowledge Base (DB)
        - README.md (使い方ガイド)
        - run_inference.py (推論実行スクリプト)
        - config.json (設定)

        このパッケージは、単体で動作する完全な推論エンジンになります。
        """
        import zipfile
        import shutil

        logger.info("Creating standalone package with training data and DB")

        # 世代交代を実行（トレーニングデータ生成）
        succession_result = await self.prepare_succession(
            domain_id=domain_id,
            min_confidence=min_confidence
        )

        if succession_result.get("status") != "prepared":
            return succession_result

        # パッケージディレクトリ作成
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        package_name = f"null_ai_model_gen{len(self.get_succession_history())}_{timestamp}"
        package_dir = output_path / package_name
        package_dir.mkdir(exist_ok=True)

        # 1. トレーニングデータをコピー
        training_dir = package_dir / "training_data"
        training_dir.mkdir(exist_ok=True)

        for format_type, file_path in succession_result["exports"].items():
            if os.path.exists(file_path):
                dest = training_dir / os.path.basename(file_path)
                shutil.copy2(file_path, dest)
                logger.info(f"Copied training data: {file_path} -> {dest}")

        # 2. Knowledge Base (DB) をコピー
        db_dir = package_dir / "knowledge_base"
        db_dir.mkdir(exist_ok=True)

        if db_path and os.path.exists(db_path):
            db_dest = db_dir / "knowledge.iath"
            shutil.copy2(db_path, db_dest)
            logger.info(f"Copied DB: {db_path} -> {db_dest}")

            # DB統計情報を生成
            try:
                from iath_decoder import IATHDecoder
                decoder = IATHDecoder(str(db_dest))
                tiles = decoder.read_all_tiles()

                db_stats = {
                    "total_tiles": len(tiles),
                    "domains": list(set(t.get("domain_id", "unknown") for t in tiles)),
                    "export_date": datetime.now().isoformat()
                }

                with open(db_dir / "db_stats.json", "w", encoding="utf-8") as f:
                    json.dump(db_stats, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"Failed to generate DB stats: {e}")

        # 3. README.md を生成
        readme_content = f"""# NullAI Model Package - Generation {len(self.get_succession_history())}

## 📦 パッケージ概要

このパッケージは、NullAI倒木システム（NurseLog System）によって生成された
完全なスタンドアロン推論エンジンです。

生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
世代: {len(self.get_succession_history())}
{"対象ドメイン: " + domain_id if domain_id else "全ドメイン"}
トレーニングデータ数: {succession_result['count']}

## 🌲 倒木システムとは

森林の倒木が次世代の栄養源となるように、古いモデルの知識を新モデルに継承する
世代交代システムです。このパッケージには、蓄積された高品質な推論データと
Knowledge Baseが含まれています。

## 📁 含まれるファイル

### training_data/
- `*.jsonl`: ChatML/Instruction/Completion形式のトレーニングデータ
- `*.csv`: CSV形式のトレーニングデータ
- `*.parquet`: Parquet形式（オプション）
- `dataset_*/`: HuggingFace Datasets形式（オプション）

### knowledge_base/
- `knowledge.iath`: IATH形式の知識ベース
- `db_stats.json`: DB統計情報

### その他
- `README.md`: このファイル
- `run_inference.py`: 推論実行スクリプト
- `config.json`: 設定ファイル

## 🚀 使い方

### 1. ファインチューニング

```bash
# HuggingFace Transformersを使用
from datasets import load_from_disk
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer

# データセットをロード
dataset = load_from_disk("training_data/dataset_*")

# モデルをロード
model = AutoModelForCausalLM.from_pretrained("your-base-model")
tokenizer = AutoTokenizer.from_pretrained("your-base-model")

# ファインチューニング
trainer = Trainer(
    model=model,
    args=TrainingArguments(output_dir="./output"),
    train_dataset=dataset
)
trainer.train()
```

### 2. 推論実行

```bash
# 付属のKnowledge Baseを使用して推論
python run_inference.py --question "あなたの質問" --db knowledge_base/knowledge.iath

# または、ファインチューニング後のモデルを使用
python run_inference.py --model ./output/checkpoint-1000 --question "質問"
```

### 3. Knowledge Baseの編集

```bash
# DBを直接編集（自由に編集可能）
python -c "from iath_decoder import IATHDecoder; decoder = IATHDecoder('knowledge_base/knowledge.iath'); print(decoder.read_all_tiles())"

# または、バックアップしてから編集
cp knowledge_base/knowledge.iath knowledge_base/knowledge.iath.backup
# 編集...
```

## 🔧 カスタマイズ

このパッケージは完全にオープンです。自由に：
- ✅ トレーニングデータの追加・削除
- ✅ Knowledge Baseの編集
- ✅ 独自ドメインの追加
- ✅ フォークして独自バージョンを作成
- ✅ 他のプロジェクトでの使用

## 📊 統計情報

- トレーニングサンプル数: {succession_result['count']}
- 最小信頼度: {min_confidence}
- エクスポート形式: {', '.join(succession_result['exports'].keys())}

## 📜 ライセンス

このパッケージは、NullAIプロジェクトの一部として提供されています。
自由に使用、編集、再配布できます。

## 🌐 サポート

- GitHub: https://github.com/your-org/null-ai
- ドキュメント: https://null-ai-docs.example.com
- 問い合わせ: support@null-ai.example.com

---

**Generated by NullAI NurseLog System v1.0.0**
"""

        with open(package_dir / "README.md", "w", encoding="utf-8") as f:
            f.write(readme_content)

        # 4. run_inference.py を生成
        inference_script = """#!/usr/bin/env python3
\"\"\"
NullAI Standalone Inference Runner

このスクリプトは、パッケージに含まれるKnowledge Baseを使用して推論を実行します。
\"\"\"
import argparse
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_inference(question: str, db_path: str = "knowledge_base/knowledge.iath", model_path: str = None):
    \"\"\"推論を実行\"\"\"
    print(f"Question: {question}")
    print(f"Using DB: {db_path}")

    if model_path:
        print(f"Using Model: {model_path}")
        # ファインチューニング済みモデルを使用
        # TODO: モデルロードと推論の実装
    else:
        # Knowledge Baseから推論
        from iath_decoder import IATHDecoder
        decoder = IATHDecoder(db_path)
        tiles = decoder.read_all_tiles()

        # 簡単な類似度検索
        relevant_tiles = []
        for tile in tiles:
            content = tile.get("content", "")
            if any(word.lower() in content.lower() for word in question.split()):
                relevant_tiles.append(tile)

        if relevant_tiles:
            print("\\nRelevant Knowledge:")
            for tile in relevant_tiles[:3]:
                print(f"- {tile.get('topic', 'Unknown')}: {tile.get('content', '')[:200]}...")
        else:
            print("\\nNo relevant knowledge found in the database.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NullAI Inference Runner")
    parser.add_argument("--question", type=str, required=True, help="Question to answer")
    parser.add_argument("--db", type=str, default="knowledge_base/knowledge.iath", help="Knowledge Base path")
    parser.add_argument("--model", type=str, help="Fine-tuned model path (optional)")

    args = parser.parse_args()
    run_inference(args.question, args.db, args.model)
"""

        with open(package_dir / "run_inference.py", "w", encoding="utf-8") as f:
            f.write(inference_script)

        os.chmod(package_dir / "run_inference.py", 0o755)

        # 5. config.json を生成
        config = {
            "package": {
                "name": package_name,
                "generation": len(self.get_succession_history()),
                "created_at": datetime.now().isoformat(),
                "domain": domain_id,
                "version": "1.0.0"
            },
            "training_data": {
                "count": succession_result['count'],
                "min_confidence": min_confidence,
                "formats": list(succession_result['exports'].keys())
            },
            "knowledge_base": {
                "path": "knowledge_base/knowledge.iath",
                "format": "iath",
                "version": "1.0"
            },
            "usage": {
                "inference_script": "run_inference.py",
                "fine_tuning": "See README.md for instructions"
            }
        }

        with open(package_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # 6. ZIPファイルに圧縮
        zip_path = output_path / f"{package_name}.zip"

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(package_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, output_path)
                    zipf.write(file_path, arcname)

        logger.info(f"Standalone package created: {zip_path}")

        # ディレクトリを削除（ZIPのみ残す）
        shutil.rmtree(package_dir)

        return {
            "status": "success",
            "package_path": str(zip_path),
            "package_name": package_name,
            "training_data_count": succession_result['count'],
            "generation": len(self.get_succession_history()),
            "size_bytes": os.path.getsize(zip_path)
        }


class DBArchiveManager:
    """DB保管システム"""

    def __init__(self, archive_dir: str = "db_archives"):
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot(
        self,
        db_path: str,
        generation: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """DBスナップショットを作成"""
        import shutil

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"generation_{generation:03d}_{timestamp}.iath"
        snapshot_path = self.archive_dir / snapshot_name

        # DBファイルをコピー
        if os.path.exists(db_path):
            shutil.copy2(db_path, snapshot_path)

            # メタデータを保存
            metadata_path = snapshot_path.with_suffix(".json")
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump({
                    "generation": generation,
                    "timestamp": datetime.now().isoformat(),
                    "original_path": db_path,
                    "snapshot_path": str(snapshot_path),
                    "metadata": metadata or {}
                }, f, indent=2, ensure_ascii=False)

            logger.info(f"Created DB snapshot: {snapshot_path}")
            return str(snapshot_path)
        else:
            logger.error(f"DB file not found: {db_path}")
            raise FileNotFoundError(f"DB file not found: {db_path}")

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """スナップショット一覧を取得"""
        snapshots = []

        for metadata_file in sorted(self.archive_dir.glob("*.json")):
            with open(metadata_file, "r", encoding="utf-8") as f:
                snapshots.append(json.load(f))

        return snapshots

    def restore_snapshot(
        self,
        snapshot_path: str,
        target_path: str
    ) -> bool:
        """スナップショットを復元"""
        import shutil

        if not os.path.exists(snapshot_path):
            logger.error(f"Snapshot not found: {snapshot_path}")
            return False

        # バックアップを作成
        if os.path.exists(target_path):
            backup_path = f"{target_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(target_path, backup_path)
            logger.info(f"Created backup: {backup_path}")

        # スナップショットを復元
        shutil.copy2(snapshot_path, target_path)
        logger.info(f"Restored snapshot {snapshot_path} to {target_path}")

        return True


# CLI用の便利関数
async def run_succession(
    domain_id: Optional[str] = None,
    min_confidence: float = 0.8,
    db_path: Optional[str] = None
):
    """世代交代を実行"""
    history_manager = InferenceHistory()
    exporter = TrainingDataExporter()
    succession_manager = ModelSuccessionManager(history_manager, exporter)

    # 世代交代準備
    result = await succession_manager.prepare_succession(
        domain_id=domain_id,
        min_confidence=min_confidence
    )

    print(f"\n=== Succession Result ===")
    print(f"Status: {result['status']}")
    print(f"Records: {result['count']}")
    print(f"\nExported files:")
    for format_type, path in result.get("exports", {}).items():
        print(f"  {format_type}: {path}")

    # DBスナップショットを作成
    if db_path and os.path.exists(db_path):
        archive_manager = DBArchiveManager()
        succession_history = succession_manager.get_succession_history()
        generation = len(succession_history)

        snapshot_path = archive_manager.create_snapshot(
            db_path=db_path,
            generation=generation,
            metadata={"succession_result": result}
        )
        print(f"\nDB Snapshot: {snapshot_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NullAI NurseLog System")
    parser.add_argument("--domain", type=str, help="Domain ID to filter")
    parser.add_argument("--min-confidence", type=float, default=0.8, help="Minimum confidence")
    parser.add_argument("--db-path", type=str, help="Database path for snapshot")

    args = parser.parse_args()

    asyncio.run(run_succession(
        domain_id=args.domain,
        min_confidence=args.min_confidence,
        db_path=args.db_path
    ))
