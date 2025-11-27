"""
NullAI Fine-tuning Dataset Creator
Creates training dataset from Knowledge Tiles for DeepSeek R1 fine-tuning
"""

import sqlite3
import json
import os
from typing import List, Dict

def extract_knowledge_tiles_from_db(db_path: str = "sql_app.db") -> List[Dict]:
    """Extract knowledge tiles from database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all knowledge tiles
    cursor.execute("""
        SELECT id, content, domain, certainty, specificity,
               source_reference, expert_verified, verification_status
        FROM knowledge_tiles
        WHERE content IS NOT NULL AND content != ''
        ORDER BY id
    """)

    tiles = []
    for row in cursor.fetchall():
        tile_id, content, domain, certainty, specificity, source, verified, status = row
        tiles.append({
            "id": tile_id,
            "content": content,
            "domain": domain,
            "certainty": certainty,
            "specificity": specificity,
            "source": source,
            "verified": verified,
            "status": status
        })

    conn.close()
    print(f"✓ Extracted {len(tiles)} knowledge tiles from database")
    return tiles


def create_instruction_dataset(tiles: List[Dict]) -> List[Dict]:
    """
    Convert knowledge tiles to instruction-following format
    Format: {"instruction": str, "input": str, "output": str}
    """
    dataset = []

    for tile in tiles:
        domain = tile.get("domain", "general")
        content = tile.get("content", "")
        verified = tile.get("verified", False)
        certainty = tile.get("certainty", 0.5)

        # Create various instruction types

        # Type 1: Direct question about the knowledge
        instruction_variants = [
            f"You are a {domain} expert. Provide accurate information based on verified knowledge tiles.",
            f"As an expert in {domain}, explain the following concept clearly.",
            f"Using your expertise in {domain}, provide detailed information.",
        ]

        # Extract key concepts from content
        if len(content) > 50:
            # Create Q&A pairs
            for inst_template in instruction_variants[:1]:  # Use first template
                dataset.append({
                    "instruction": inst_template,
                    "input": f"Explain about: {content[:100]}...",
                    "output": content,
                    "metadata": {
                        "domain": domain,
                        "tile_id": tile["id"],
                        "verified": verified,
                        "certainty": certainty
                    }
                })

        # Type 2: Domain-specific queries
        if domain == "medical":
            dataset.append({
                "instruction": "Provide evidence-based medical information. Always recommend consulting healthcare professionals for medical decisions.",
                "input": f"What should I know about this medical topic?",
                "output": f"{content}\n\nIMPORTANT: This information is for educational purposes only. Always consult qualified healthcare professionals for medical advice and decisions.",
                "metadata": {
                    "domain": domain,
                    "tile_id": tile["id"],
                    "verified": verified,
                    "certainty": certainty
                }
            })
        elif domain == "legal":
            dataset.append({
                "instruction": "Provide legal information based on verified sources. This is not legal advice.",
                "input": f"What legal information can you provide about this topic?",
                "output": f"{content}\n\nDISCLAIMER: This is informational only and not legal advice. Consult a licensed attorney for legal matters.",
                "metadata": {
                    "domain": domain,
                    "tile_id": tile["id"],
                    "verified": verified,
                    "certainty": certainty
                }
            })
        else:
            dataset.append({
                "instruction": f"Provide accurate information about {domain} based on verified knowledge.",
                "input": f"Tell me about this {domain} concept.",
                "output": content,
                "metadata": {
                    "domain": domain,
                    "tile_id": tile["id"],
                    "verified": verified,
                    "certainty": certainty
                }
            })

    print(f"✓ Created {len(dataset)} training examples")
    return dataset


def save_dataset(dataset: List[Dict], output_path: str):
    """Save dataset in JSONL format for fine-tuning"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in dataset:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    print(f"✓ Saved dataset to {output_path}")


def create_alpaca_format(dataset: List[Dict], output_path: str):
    """Convert to Alpaca format for compatibility"""
    alpaca_dataset = []
    for item in dataset:
        alpaca_item = {
            "instruction": item["instruction"],
            "input": item.get("input", ""),
            "output": item["output"]
        }
        alpaca_dataset.append(alpaca_item)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(alpaca_dataset, f, ensure_ascii=False, indent=2)
    print(f"✓ Saved Alpaca format dataset to {output_path}")


def main():
    print("\n" + "="*60)
    print("NullAI Fine-tuning Dataset Creator")
    print("="*60 + "\n")

    # Extract knowledge tiles
    tiles = extract_knowledge_tiles_from_db("sql_app.db")

    if len(tiles) == 0:
        print("⚠️  No knowledge tiles found in database")
        return

    # Create instruction dataset
    dataset = create_instruction_dataset(tiles)

    # Create output directory
    os.makedirs("finetune_data", exist_ok=True)

    # Save in multiple formats
    save_dataset(dataset, "finetune_data/nullai_dataset.jsonl")
    create_alpaca_format(dataset, "finetune_data/nullai_dataset_alpaca.json")

    # Create train/validation split (90/10)
    split_idx = int(len(dataset) * 0.9)
    train_dataset = dataset[:split_idx]
    val_dataset = dataset[split_idx:]

    save_dataset(train_dataset, "finetune_data/train.jsonl")
    save_dataset(val_dataset, "finetune_data/validation.jsonl")

    print(f"\n✅ Dataset creation complete!")
    print(f"   Total examples: {len(dataset)}")
    print(f"   Training: {len(train_dataset)}")
    print(f"   Validation: {len(val_dataset)}")
    print(f"   Output directory: finetune_data/\n")


if __name__ == "__main__":
    main()
