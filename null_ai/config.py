"""
NullAI - 汎用知識推論システム設定

マルチドメイン対応の推論エンジン設定を管理する。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import json
import os


class ModelProvider(str, Enum):
    """
    対応するLLMプロバイダー

    注意: OpenAI/Anthropic等の競合APIは利用規約上の理由から削除されました。
    NullAIは独自モデルまたはオープンソースモデルのみをサポートします。
    """
    MLX = "mlx"                       # MLX (Apple Silicon専用、最速)
    HUGGINGFACE = "huggingface"       # HuggingFace Transformers (推奨)
    HUGGINGFACE_API = "huggingface_api"  # HuggingFace Inference API
    LOCAL = "local"                   # ローカルモデル（Transformers）
    GGUF = "gguf"                     # GGUF形式（llama.cpp互換）
    OLLAMA = "ollama"                 # Ollama（ローカル推論サーバー）


@dataclass
class ModelConfig:
    """個別モデルの設定"""
    model_id: str
    display_name: str
    provider: ModelProvider
    api_url: str = ""
    api_key: str = ""  # 環境変数から読み込み推奨
    model_name: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 120
    is_default: bool = False
    supported_domains: List[str] = field(default_factory=lambda: ["general"])
    description: str = ""

    def to_dict(self) -> Dict:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "provider": self.provider.value,
            "api_url": self.api_url,
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "is_default": self.is_default,
            "supported_domains": self.supported_domains,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ModelConfig":
        return cls(
            model_id=data["model_id"],
            display_name=data["display_name"],
            provider=ModelProvider(data["provider"]),
            api_url=data.get("api_url", ""),
            api_key=data.get("api_key", ""),
            model_name=data.get("model_name", ""),
            max_tokens=data.get("max_tokens", 4096),
            temperature=data.get("temperature", 0.7),
            timeout=data.get("timeout", 120),
            is_default=data.get("is_default", False),
            supported_domains=data.get("supported_domains", ["general"]),
            description=data.get("description", "")
        )


@dataclass
class DomainConfig:
    """ドメイン（ジャンル）の設定"""
    domain_id: str
    name: str
    description: str
    default_model_id: Optional[str] = None
    db_path: str = ""
    ontology_path: str = ""
    icon: str = ""
    is_active: bool = True

    def to_dict(self) -> Dict:
        return {
            "domain_id": self.domain_id,
            "name": self.name,
            "description": self.description,
            "default_model_id": self.default_model_id,
            "db_path": self.db_path,
            "ontology_path": self.ontology_path,
            "icon": self.icon,
            "is_active": self.is_active
        }


@dataclass
class NullAIConfig:
    """NullAIシステム全体の設定"""
    system_name: str = "NullAI"
    version: str = "1.0.0"
    debug: bool = False

    # デフォルトモデル設定
    default_model_id: str = "deepseek-r1-32b"

    # 記憶システム設定
    memory_max_nodes: int = 100000
    auto_save_to_memory: bool = True  # 推論結果を自動保存
    memory_save_threshold: float = 0.6  # この信頼度以上なら保存

    # 継続学習設定
    enable_nurse_log_system: bool = True
    succession_threshold: float = 0.85
    dream_interval_conversations: int = 50

    # API設定
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: List[str] = field(default_factory=lambda: ["*"])

    # DB設定
    main_db_path: str = "null_ai_knowledge.iath"
    config_path: str = "null_ai_config.json"

    def to_dict(self) -> Dict:
        return {
            "system_name": self.system_name,
            "version": self.version,
            "debug": self.debug,
            "default_model_id": self.default_model_id,
            "memory_max_nodes": self.memory_max_nodes,
            "auto_save_to_memory": self.auto_save_to_memory,
            "memory_save_threshold": self.memory_save_threshold,
            "enable_nurse_log_system": self.enable_nurse_log_system,
            "succession_threshold": self.succession_threshold,
            "dream_interval_conversations": self.dream_interval_conversations,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "cors_origins": self.cors_origins,
            "main_db_path": self.main_db_path
        }


# デフォルトモデル設定
# 注意: HuggingFaceおよびローカルモデルのみをサポート
# 外部API（OpenAI/Anthropic等）は利用規約上の理由から削除されました
DEFAULT_MODELS: List[ModelConfig] = [
    ModelConfig(
        model_id="deepseek-r1-32b",
        display_name="DeepSeek R1 32B",
        provider=ModelProvider.HUGGINGFACE,
        model_name="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        max_tokens=4096,
        temperature=0.7,
        is_default=True,
        supported_domains=["medical", "legal", "economics", "general"],
        description="高性能な推論特化モデル。医療・法律・経済に対応。"
    ),
    ModelConfig(
        model_id="deepseek-r1-14b",
        display_name="DeepSeek R1 14B",
        provider=ModelProvider.HUGGINGFACE,
        model_name="deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
        max_tokens=4096,
        temperature=0.7,
        supported_domains=["general"],
        description="軽量版DeepSeek。一般的な質問に適している。"
    ),
    ModelConfig(
        model_id="deepseek-r1-7b",
        display_name="DeepSeek R1 7B",
        provider=ModelProvider.HUGGINGFACE,
        model_name="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        max_tokens=4096,
        temperature=0.7,
        supported_domains=["general"],
        description="最軽量版DeepSeek。リソース制限環境向け。"
    ),
    ModelConfig(
        model_id="llama3-8b",
        display_name="Llama 3.1 8B",
        provider=ModelProvider.HUGGINGFACE,
        model_name="meta-llama/Llama-3.1-8B-Instruct",
        max_tokens=4096,
        temperature=0.7,
        supported_domains=["general", "programming"],
        description="Meta社の汎用LLM。プログラミングに強い。"
    ),
    ModelConfig(
        model_id="qwen2-7b",
        display_name="Qwen2.5 7B",
        provider=ModelProvider.HUGGINGFACE,
        model_name="Qwen/Qwen2.5-7B-Instruct",
        max_tokens=4096,
        temperature=0.7,
        supported_domains=["general", "programming"],
        description="Alibaba社の高性能多言語モデル。日本語に強い。"
    ),
    ModelConfig(
        model_id="mistral-7b",
        display_name="Mistral 7B",
        provider=ModelProvider.HUGGINGFACE,
        model_name="mistralai/Mistral-7B-Instruct-v0.3",
        max_tokens=4096,
        temperature=0.7,
        supported_domains=["general"],
        description="Mistral AIの高効率モデル。バランスの良い性能。"
    ),
    # === Ollamaモデル（ローカル推論サーバー） ===
    ModelConfig(
        model_id="ollama-deepseek-r1-32b",
        display_name="Ollama DeepSeek R1 32B",
        provider=ModelProvider.OLLAMA,
        model_name="deepseek-r1:32b",
        max_tokens=8192,
        temperature=0.7,
        supported_domains=["general", "medical", "legal", "economics"],
        description="Ollama経由でDeepSeek R1 32Bを使用。推論特化型。"
    ),
    ModelConfig(
        model_id="ollama-deepseek-r1-70b",
        display_name="Ollama DeepSeek R1 70B",
        provider=ModelProvider.OLLAMA,
        model_name="deepseek-r1:70b",
        max_tokens=8192,
        temperature=0.7,
        supported_domains=["general", "medical", "legal"],
        description="Ollama経由でDeepSeek R1 70Bを使用。最高品質の推論。"
    ),
    ModelConfig(
        model_id="ollama-gemma3-12b",
        display_name="Ollama Gemma 3 12B",
        provider=ModelProvider.OLLAMA,
        model_name="gemma3:12b",
        max_tokens=4096,
        temperature=0.7,
        supported_domains=["general", "programming"],
        description="Ollama経由でGemma 3 12Bを使用。Google製高性能モデル。"
    ),
    ModelConfig(
        model_id="ollama-codegemma",
        display_name="Ollama CodeGemma",
        provider=ModelProvider.OLLAMA,
        model_name="codegemma:latest",
        max_tokens=4096,
        temperature=0.7,
        supported_domains=["programming"],
        description="Ollama経由でCodeGemmaを使用。コード生成特化。"
    )
]

# デフォルトドメイン設定（大幅拡張版）
DEFAULT_DOMAINS: List[DomainConfig] = [
    # === 医療・健康カテゴリ ===
    DomainConfig(
        domain_id="medical",
        name="Medical (General)",
        description="医療・健康に関する一般的な知識領域",
        default_model_id="deepseek-r1-32b",
        db_path="medical_knowledge.iath",
        ontology_path="cardiology_ontology.json",
        icon="medical",
        is_active=True
    ),
    DomainConfig(
        domain_id="cardiology",
        name="Cardiology",
        description="循環器・心臓病学",
        default_model_id="deepseek-r1-32b",
        icon="heart",
        is_active=True
    ),
    DomainConfig(
        domain_id="neurology",
        name="Neurology",
        description="神経学・脳科学",
        default_model_id="deepseek-r1-32b",
        icon="brain",
        is_active=True
    ),
    DomainConfig(
        domain_id="oncology",
        name="Oncology",
        description="腫瘍学・がん医療",
        default_model_id="deepseek-r1-32b",
        icon="oncology",
        is_active=True
    ),
    DomainConfig(
        domain_id="pediatrics",
        name="Pediatrics",
        description="小児科学・子どもの健康",
        default_model_id="deepseek-r1-32b",
        icon="child",
        is_active=True
    ),
    DomainConfig(
        domain_id="psychiatry",
        name="Psychiatry",
        description="精神医学・メンタルヘルス",
        default_model_id="deepseek-r1-32b",
        icon="mind",
        is_active=True
    ),
    DomainConfig(
        domain_id="pharmacology",
        name="Pharmacology",
        description="薬理学・薬物療法",
        default_model_id="deepseek-r1-32b",
        icon="pill",
        is_active=True
    ),
    DomainConfig(
        domain_id="nutrition",
        name="Nutrition",
        description="栄養学・食事療法",
        default_model_id="deepseek-r1-32b",
        icon="nutrition",
        is_active=True
    ),

    # === 法律カテゴリ ===
    DomainConfig(
        domain_id="legal",
        name="Legal (General)",
        description="法律・法務に関する一般的な知識領域",
        default_model_id="deepseek-r1-32b",
        db_path="legal_knowledge.iath",
        ontology_path="legal_ontology.json",
        icon="legal",
        is_active=True
    ),
    DomainConfig(
        domain_id="labor_law",
        name="Labor Law",
        description="労働法・雇用法規",
        default_model_id="deepseek-r1-32b",
        icon="labor",
        is_active=True
    ),
    DomainConfig(
        domain_id="corporate_law",
        name="Corporate Law",
        description="会社法・企業法務",
        default_model_id="deepseek-r1-32b",
        icon="corporate",
        is_active=True
    ),
    DomainConfig(
        domain_id="intellectual_property",
        name="Intellectual Property",
        description="知的財産権・特許・著作権",
        default_model_id="deepseek-r1-32b",
        icon="ip",
        is_active=True
    ),
    DomainConfig(
        domain_id="contract_law",
        name="Contract Law",
        description="契約法・取引法務",
        default_model_id="deepseek-r1-32b",
        icon="contract",
        is_active=True
    ),
    DomainConfig(
        domain_id="tax_law",
        name="Tax Law",
        description="税法・租税法規",
        default_model_id="deepseek-r1-32b",
        icon="tax",
        is_active=True
    ),
    DomainConfig(
        domain_id="family_law",
        name="Family Law",
        description="家族法・相続法",
        default_model_id="deepseek-r1-32b",
        icon="family",
        is_active=True
    ),
    DomainConfig(
        domain_id="criminal_law",
        name="Criminal Law",
        description="刑事法・刑法",
        default_model_id="deepseek-r1-32b",
        icon="criminal",
        is_active=True
    ),

    # === 経済・金融カテゴリ ===
    DomainConfig(
        domain_id="economics",
        name="Economics (General)",
        description="経済学・経済理論",
        default_model_id="deepseek-r1-32b",
        db_path="economics_knowledge.iath",
        icon="economics",
        is_active=True
    ),
    DomainConfig(
        domain_id="finance",
        name="Finance",
        description="金融・投資・資産運用",
        default_model_id="deepseek-r1-32b",
        icon="finance",
        is_active=True
    ),
    DomainConfig(
        domain_id="accounting",
        name="Accounting",
        description="会計学・財務会計",
        default_model_id="deepseek-r1-32b",
        icon="accounting",
        is_active=True
    ),
    DomainConfig(
        domain_id="banking",
        name="Banking",
        description="銀行業務・金融機関",
        default_model_id="deepseek-r1-32b",
        icon="bank",
        is_active=True
    ),
    DomainConfig(
        domain_id="cryptocurrency",
        name="Cryptocurrency",
        description="暗号資産・ブロックチェーン金融",
        default_model_id="deepseek-r1-32b",
        icon="crypto",
        is_active=True
    ),
    DomainConfig(
        domain_id="real_estate",
        name="Real Estate",
        description="不動産・不動産投資",
        default_model_id="deepseek-r1-32b",
        icon="realestate",
        is_active=True
    ),

    # === テクノロジー・IT カテゴリ ===
    DomainConfig(
        domain_id="programming",
        name="Programming",
        description="プログラミング・ソフトウェア開発",
        default_model_id="llama3-8b",
        icon="code",
        is_active=True
    ),
    DomainConfig(
        domain_id="web_development",
        name="Web Development",
        description="Web開発・フロントエンド・バックエンド",
        default_model_id="llama3-8b",
        icon="web",
        is_active=True
    ),
    DomainConfig(
        domain_id="machine_learning",
        name="Machine Learning",
        description="機械学習・AI・ディープラーニング",
        default_model_id="deepseek-r1-32b",
        icon="ml",
        is_active=True
    ),
    DomainConfig(
        domain_id="cybersecurity",
        name="Cybersecurity",
        description="サイバーセキュリティ・情報セキュリティ",
        default_model_id="deepseek-r1-32b",
        icon="security",
        is_active=True
    ),
    DomainConfig(
        domain_id="cloud_computing",
        name="Cloud Computing",
        description="クラウドコンピューティング・AWS/GCP/Azure",
        default_model_id="llama3-8b",
        icon="cloud",
        is_active=True
    ),
    DomainConfig(
        domain_id="devops",
        name="DevOps",
        description="DevOps・CI/CD・インフラ自動化",
        default_model_id="llama3-8b",
        icon="devops",
        is_active=True
    ),
    DomainConfig(
        domain_id="databases",
        name="Databases",
        description="データベース・SQL・NoSQL",
        default_model_id="llama3-8b",
        icon="database",
        is_active=True
    ),
    DomainConfig(
        domain_id="mobile_development",
        name="Mobile Development",
        description="モバイルアプリ開発・iOS/Android",
        default_model_id="llama3-8b",
        icon="mobile",
        is_active=True
    ),

    # === 科学・学術カテゴリ ===
    DomainConfig(
        domain_id="physics",
        name="Physics",
        description="物理学・力学・量子力学",
        default_model_id="deepseek-r1-32b",
        icon="physics",
        is_active=True
    ),
    DomainConfig(
        domain_id="chemistry",
        name="Chemistry",
        description="化学・有機化学・無機化学",
        default_model_id="deepseek-r1-32b",
        icon="chemistry",
        is_active=True
    ),
    DomainConfig(
        domain_id="biology",
        name="Biology",
        description="生物学・分子生物学・遺伝学",
        default_model_id="deepseek-r1-32b",
        icon="biology",
        is_active=True
    ),
    DomainConfig(
        domain_id="mathematics",
        name="Mathematics",
        description="数学・統計学・確率論",
        default_model_id="deepseek-r1-32b",
        icon="math",
        is_active=True
    ),
    DomainConfig(
        domain_id="environmental_science",
        name="Environmental Science",
        description="環境科学・生態学・気候変動",
        default_model_id="deepseek-r1-32b",
        icon="environment",
        is_active=True
    ),
    DomainConfig(
        domain_id="astronomy",
        name="Astronomy",
        description="天文学・宇宙科学",
        default_model_id="deepseek-r1-32b",
        icon="astronomy",
        is_active=True
    ),

    # === ビジネス・マネジメントカテゴリ ===
    DomainConfig(
        domain_id="business_strategy",
        name="Business Strategy",
        description="経営戦略・ビジネスプランニング",
        default_model_id="deepseek-r1-32b",
        icon="strategy",
        is_active=True
    ),
    DomainConfig(
        domain_id="marketing",
        name="Marketing",
        description="マーケティング・広告・ブランディング",
        default_model_id="deepseek-r1-32b",
        icon="marketing",
        is_active=True
    ),
    DomainConfig(
        domain_id="human_resources",
        name="Human Resources",
        description="人事・採用・組織開発",
        default_model_id="deepseek-r1-32b",
        icon="hr",
        is_active=True
    ),
    DomainConfig(
        domain_id="project_management",
        name="Project Management",
        description="プロジェクト管理・アジャイル・スクラム",
        default_model_id="deepseek-r1-32b",
        icon="project",
        is_active=True
    ),
    DomainConfig(
        domain_id="entrepreneurship",
        name="Entrepreneurship",
        description="起業・スタートアップ・ベンチャー",
        default_model_id="deepseek-r1-32b",
        icon="startup",
        is_active=True
    ),
    DomainConfig(
        domain_id="supply_chain",
        name="Supply Chain",
        description="サプライチェーン・物流・在庫管理",
        default_model_id="deepseek-r1-32b",
        icon="logistics",
        is_active=True
    ),

    # === 教育・学習カテゴリ ===
    DomainConfig(
        domain_id="education",
        name="Education",
        description="教育学・教育方法・カリキュラム設計",
        default_model_id="deepseek-r1-32b",
        icon="education",
        is_active=True
    ),
    DomainConfig(
        domain_id="language_learning",
        name="Language Learning",
        description="語学学習・外国語教育",
        default_model_id="qwen2-7b",
        icon="language",
        is_active=True
    ),
    DomainConfig(
        domain_id="history",
        name="History",
        description="歴史学・世界史・日本史",
        default_model_id="deepseek-r1-32b",
        icon="history",
        is_active=True
    ),
    DomainConfig(
        domain_id="philosophy",
        name="Philosophy",
        description="哲学・倫理学・論理学",
        default_model_id="deepseek-r1-32b",
        icon="philosophy",
        is_active=True
    ),

    # === 工学・製造カテゴリ ===
    DomainConfig(
        domain_id="mechanical_engineering",
        name="Mechanical Engineering",
        description="機械工学・機械設計",
        default_model_id="deepseek-r1-32b",
        icon="mechanical",
        is_active=True
    ),
    DomainConfig(
        domain_id="electrical_engineering",
        name="Electrical Engineering",
        description="電気工学・電子工学",
        default_model_id="deepseek-r1-32b",
        icon="electrical",
        is_active=True
    ),
    DomainConfig(
        domain_id="civil_engineering",
        name="Civil Engineering",
        description="土木工学・建設工学",
        default_model_id="deepseek-r1-32b",
        icon="civil",
        is_active=True
    ),
    DomainConfig(
        domain_id="architecture",
        name="Architecture",
        description="建築学・建築設計",
        default_model_id="deepseek-r1-32b",
        icon="architecture",
        is_active=True
    ),
    DomainConfig(
        domain_id="manufacturing",
        name="Manufacturing",
        description="製造業・生産管理・品質管理",
        default_model_id="deepseek-r1-32b",
        icon="manufacturing",
        is_active=True
    ),
    DomainConfig(
        domain_id="robotics",
        name="Robotics",
        description="ロボット工学・自動化",
        default_model_id="deepseek-r1-32b",
        icon="robot",
        is_active=True
    ),

    # === ライフスタイルカテゴリ ===
    DomainConfig(
        domain_id="cooking",
        name="Cooking",
        description="料理・レシピ・調理技術",
        default_model_id="qwen2-7b",
        icon="cooking",
        is_active=True
    ),
    DomainConfig(
        domain_id="fitness",
        name="Fitness",
        description="フィットネス・運動・トレーニング",
        default_model_id="qwen2-7b",
        icon="fitness",
        is_active=True
    ),
    DomainConfig(
        domain_id="travel",
        name="Travel",
        description="旅行・観光・地理",
        default_model_id="qwen2-7b",
        icon="travel",
        is_active=True
    ),
    DomainConfig(
        domain_id="gardening",
        name="Gardening",
        description="園芸・ガーデニング・植物栽培",
        default_model_id="qwen2-7b",
        icon="gardening",
        is_active=True
    ),
    DomainConfig(
        domain_id="diy",
        name="DIY & Home Improvement",
        description="DIY・日曜大工・住宅改修",
        default_model_id="qwen2-7b",
        icon="diy",
        is_active=True
    ),

    # === 芸術・クリエイティブカテゴリ ===
    DomainConfig(
        domain_id="music",
        name="Music",
        description="音楽理論・作曲・楽器演奏",
        default_model_id="qwen2-7b",
        icon="music",
        is_active=True
    ),
    DomainConfig(
        domain_id="visual_arts",
        name="Visual Arts",
        description="美術・絵画・彫刻",
        default_model_id="qwen2-7b",
        icon="art",
        is_active=True
    ),
    DomainConfig(
        domain_id="photography",
        name="Photography",
        description="写真撮影・画像編集",
        default_model_id="qwen2-7b",
        icon="camera",
        is_active=True
    ),
    DomainConfig(
        domain_id="writing",
        name="Writing",
        description="文章作成・クリエイティブライティング",
        default_model_id="qwen2-7b",
        icon="writing",
        is_active=True
    ),
    DomainConfig(
        domain_id="game_development",
        name="Game Development",
        description="ゲーム開発・ゲームデザイン",
        default_model_id="llama3-8b",
        icon="game",
        is_active=True
    ),

    # === 一般・その他 ===
    DomainConfig(
        domain_id="general",
        name="General",
        description="一般的な質問・雑学",
        default_model_id="deepseek-r1-32b",
        icon="general",
        is_active=True
    ),
]


class ConfigManager:
    """設定の読み書きを管理"""

    def __init__(self, config_dir: str = "."):
        self.config_dir = config_dir
        self.models_path = os.path.join(config_dir, "models_config.json")
        self.domains_path = os.path.join(config_dir, "domains_config.json")
        self.system_path = os.path.join(config_dir, "null_ai_config.json")

        self.models: Dict[str, ModelConfig] = {}
        self.domains: Dict[str, DomainConfig] = {}
        self.system_config = NullAIConfig()

        self._load_or_create_defaults()

    def _load_or_create_defaults(self):
        """設定ファイルを読み込むか、デフォルトを作成"""
        # モデル設定
        if os.path.exists(self.models_path):
            with open(self.models_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for m in data.get("models", []):
                    config = ModelConfig.from_dict(m)
                    self.models[config.model_id] = config
        else:
            for m in DEFAULT_MODELS:
                self.models[m.model_id] = m
            self.save_models()

        # ドメイン設定
        if os.path.exists(self.domains_path):
            with open(self.domains_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for d in data.get("domains", []):
                    config = DomainConfig(**d)
                    self.domains[config.domain_id] = config
        else:
            for d in DEFAULT_DOMAINS:
                self.domains[d.domain_id] = d
            self.save_domains()

        # システム設定
        if os.path.exists(self.system_path):
            with open(self.system_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.system_config = NullAIConfig(**{
                    k: v for k, v in data.items()
                    if k in NullAIConfig.__dataclass_fields__
                })
        else:
            self.save_system_config()

    def save_models(self):
        """モデル設定を保存"""
        data = {"models": [m.to_dict() for m in self.models.values()]}
        with open(self.models_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_domains(self):
        """ドメイン設定を保存"""
        data = {"domains": [d.to_dict() for d in self.domains.values()]}
        with open(self.domains_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_system_config(self):
        """システム設定を保存"""
        with open(self.system_path, 'w', encoding='utf-8') as f:
            json.dump(self.system_config.to_dict(), f, ensure_ascii=False, indent=2)

    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """モデル設定を取得"""
        return self.models.get(model_id)

    def get_default_model(self) -> Optional[ModelConfig]:
        """デフォルトモデルを取得"""
        for m in self.models.values():
            if m.is_default:
                return m
        return list(self.models.values())[0] if self.models else None

    def get_domain(self, domain_id: str) -> Optional[DomainConfig]:
        """ドメイン設定を取得"""
        return self.domains.get(domain_id)

    def add_model(self, config: ModelConfig) -> bool:
        """モデルを追加"""
        if config.model_id in self.models:
            return False
        self.models[config.model_id] = config
        self.save_models()
        return True

    def update_model(self, config: ModelConfig) -> bool:
        """モデルを更新"""
        if config.model_id not in self.models:
            return False
        self.models[config.model_id] = config
        self.save_models()
        return True

    def delete_model(self, model_id: str) -> bool:
        """モデルを削除"""
        if model_id not in self.models:
            return False
        del self.models[model_id]
        self.save_models()
        return True

    def add_domain(self, config: DomainConfig) -> bool:
        """ドメインを追加"""
        if config.domain_id in self.domains:
            return False
        self.domains[config.domain_id] = config
        self.save_domains()
        return True

    def list_models(self, domain_id: Optional[str] = None) -> List[ModelConfig]:
        """モデル一覧を取得"""
        models = list(self.models.values())
        if domain_id:
            models = [m for m in models if domain_id in m.supported_domains or "general" in m.supported_domains]
        return models

    def list_domains(self, active_only: bool = True) -> List[DomainConfig]:
        """ドメイン一覧を取得"""
        domains = list(self.domains.values())
        if active_only:
            domains = [d for d in domains if d.is_active]
        return domains
