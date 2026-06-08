"""
Career Knowledge Base - Configuration
======================================
Tập tin cấu hình trung tâm cho toàn bộ pipeline.
Mọi đường dẫn, tham số model, và cấu hình DB đều nằm ở đây.
"""

from pathlib import Path

# ============================================================
# 1. ĐƯỜNG DẪN THƯ MỤC
# ============================================================
PROJECT_ROOT = Path(r"C:\CV feedback and roadmap")
DATA_DIR = PROJECT_ROOT / "Data"
CLEAN_DIR = DATA_DIR / "Data_clean"
KB_DIR = PROJECT_ROOT / "knowledge_base"
OUTPUT_DIR = KB_DIR / "outputs"

# Tự động tạo thư mục outputs nếu chưa tồn tại
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 2. ĐƯỜNG DẪN FILE DỮ LIỆU NGUỒN
# ============================================================
LINKEDIN_PATH = CLEAN_DIR / "linkedin_clean.xlsx"
TOPCV_PATH = CLEAN_DIR / "topcv_clean.xlsx"
JD_CSV_PATH = DATA_DIR / "JD.csv"
RESUME_CSV_PATH = DATA_DIR / "Resume.csv"

# ============================================================
# 3. ĐƯỜNG DẪN OUTPUT FILES (8 Deliverables)
# ============================================================
UNIFIED_DATA_PATH = OUTPUT_DIR / "unified_data.parquet"
DATA_WITH_SKILLS_PATH = OUTPUT_DIR / "data_with_skills.parquet"
SKILL_ONTOLOGY_PATH = OUTPUT_DIR / "skill_ontology.json"
SKILLS_MASTER_PATH = OUTPUT_DIR / "skills_master.csv"
ROLE_SKILL_MATRIX_PATH = OUTPUT_DIR / "role_skill_matrix.csv"
CAREER_GRAPH_PATH = OUTPUT_DIR / "career_graph.json"
RESUME_PROFILES_PATH = OUTPUT_DIR / "resume_profiles.parquet"
JOB_PROFILES_PATH = OUTPUT_DIR / "job_profiles.parquet"

# ============================================================
# 4. CẤU HÌNH EMBEDDING MODEL
# ============================================================
# V2.2: paraphrase-multilingual-MiniLM-L12-v2
#   - 384 dimensions (cùng dim với MiniLM-L6 nhưng quality cao hơn)
#   - Huấn luyện trên 50+ ngôn ngữ bao gồm tiếng Việt
#   - Phù hợp với data CV tiếng Việt + technical terms tiếng Anh
# Previous: sentence-transformers/all-MiniLM-L6-v2 (384 dim, English-only)
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMENSION = 384  # paraphrase-multilingual-MiniLM-L12-v2 output dimension

# ============================================================
# 5. CẤU HÌNH DATABASE (PostgreSQL + pgvector)
# ============================================================
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "career_kb",
    "user": "postgres",
    "password": "postgres",  # TODO: Đổi sang env variable trong production
}
DB_CONNECTION_STRING = (
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
)

# ============================================================
# 6. CẤU HÌNH SKILL EXTRACTION
# ============================================================
# Ngưỡng fuzzy matching để group skill variants (0-100)
FUZZY_MATCH_THRESHOLD = 85

# Số lượng top skills cần extract từ data để xây seed ontology
SEED_ONTOLOGY_TOP_N = 200

# Seed skills mặc định (fallback khi chưa có ontology từ data)
DEFAULT_SEED_SKILLS = [
    # Programming Languages
    "Python", "Java", "JavaScript", "TypeScript", "C#", "C++", "Go", "Rust",
    "PHP", "Ruby", "Swift", "Kotlin", "Scala", "R", "MATLAB", "SQL",
    # Web Frontend
    "React", "Angular", "Vue.js", "Next.js", "Svelte", "HTML", "CSS",
    "Tailwind CSS", "Bootstrap", "Webpack", "Vite",
    # Web Backend
    "Node.js", "Express", "FastAPI", "Flask", "Django", "Spring Boot",
    "ASP.NET", "Laravel", "Ruby on Rails", "NestJS",
    # Databases
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Cassandra",
    "DynamoDB", "SQLite", "MariaDB", "Neo4j",
    # Cloud & DevOps
    "AWS", "Azure", "Google Cloud Platform", "Docker", "Kubernetes",
    "Terraform", "Jenkins", "GitHub Actions", "GitLab CI", "CI/CD",
    "Ansible", "Helm", "Prometheus", "Grafana",
    # AI/ML
    "Machine Learning", "Deep Learning", "Natural Language Processing",
    "Computer Vision", "TensorFlow", "PyTorch", "Scikit-learn", "Keras",
    "Hugging Face", "Transformers", "LLM", "RAG", "LangChain", "LlamaIndex",
    "OpenAI API", "Fine-tuning", "Prompt Engineering", "MLOps",
    "Reinforcement Learning", "GAN", "Stable Diffusion",
    # Data
    "Apache Spark", "Apache Kafka", "Airflow", "dbt", "Snowflake",
    "BigQuery", "Redshift", "Pandas", "NumPy", "Matplotlib", "Seaborn",
    "Power BI", "Tableau", "Excel",
    # Tools & Practices
    "Git", "Agile", "Scrum", "Jira", "Confluence", "REST API", "GraphQL",
    "gRPC", "Microservices", "System Design", "OAuth", "JWT",
    "Unit Testing", "Integration Testing", "Selenium", "Cypress",
    # Vietnamese-specific (sẽ được bổ sung từ data)
    "Zalo Mini App", "MoMo", "VNPay",
]

# ============================================================
# 7. MANUAL ALIAS OVERRIDES
# ============================================================
# Các alias mapping cứng (không cần fuzzy matching)
MANUAL_ALIASES = {
    # Machine Learning variants
    "ml": "Machine Learning",
    "machine-learning": "Machine Learning",
    "machine learning": "Machine Learning",
    "deep-learning": "Deep Learning",
    "deep learning": "Deep Learning",
    "dl": "Deep Learning",
    # NLP variants
    "nlp": "Natural Language Processing",
    "natural-language-processing": "Natural Language Processing",
    # CV variants
    "cv": "Computer Vision",
    "computer-vision": "Computer Vision",
    # JavaScript variants
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    # Python variants
    "py": "Python",
    "python3": "Python",
    # Cloud variants
    "gcp": "Google Cloud Platform",
    "google cloud": "Google Cloud Platform",
    "aws": "AWS",
    "amazon web services": "AWS",
    "azure": "Azure",
    "microsoft azure": "Azure",
    # Framework variants
    "reactjs": "React",
    "react.js": "React",
    "angularjs": "Angular",
    "angular.js": "Angular",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "expressjs": "Express",
    "express.js": "Express",
    "nest.js": "NestJS",
    "nestjs": "NestJS",
    "springboot": "Spring Boot",
    "spring-boot": "Spring Boot",
    "asp.net core": "ASP.NET",
    "aspnet": "ASP.NET",
    # Database variants
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "elastic": "Elasticsearch",
    # DevOps variants
    "k8s": "Kubernetes",
    "docker": "Docker",
    "terraform": "Terraform",
    "gh actions": "GitHub Actions",
    "github-actions": "GitHub Actions",
    "gitlab-ci": "GitLab CI",
    "cicd": "CI/CD",
    "ci-cd": "CI/CD",
    # AI/ML tool variants
    "tf": "TensorFlow",
    "tensorflow": "TensorFlow",
    "torch": "PyTorch",
    "pytorch": "PyTorch",
    "sklearn": "Scikit-learn",
    "scikit learn": "Scikit-learn",
    "hf": "Hugging Face",
    "huggingface": "Hugging Face",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "rag": "RAG",
    "retrieval augmented generation": "RAG",
    "llm": "LLM",
    "large language model": "LLM",
    "openai": "OpenAI API",
    # Data tools
    "spark": "Apache Spark",
    "kafka": "Apache Kafka",
    "pbi": "Power BI",
    "powerbi": "Power BI",
    # Practices
    "rest": "REST API",
    "restful": "REST API",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "oauth2": "OAuth",
    "jwt": "JWT",
}

print(f"[CONFIG] Project root: {PROJECT_ROOT}")
print(f"[CONFIG] Output dir: {OUTPUT_DIR}")
print(f"[CONFIG] Embedding model: {EMBEDDING_MODEL}")
print(f"[CONFIG] Seed skills count: {len(DEFAULT_SEED_SKILLS)}")
print(f"[CONFIG] Manual aliases count: {len(MANUAL_ALIASES)}")
