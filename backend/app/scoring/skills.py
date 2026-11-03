"""A vocabulary of skills with their spellings, used to find skills in JDs and resumes.

Each entry is: canonical name -> other spellings. Matching is case-insensitive and whole-word,
except for names listed in CASE_SENSITIVE (e.g. "Go", which is also an ordinary word).
"""

import re
from functools import lru_cache

SKILLS: dict[str, list[str]] = {
    # languages
    "Python": [],
    "Java": [],
    "JavaScript": ["JS", "ECMAScript"],
    "TypeScript": ["TS"],
    "Go": ["Golang"],
    "Rust": [],
    "C++": ["CPP"],
    "C#": ["C Sharp", "CSharp"],
    "Ruby": [],
    "PHP": [],
    "Kotlin": [],
    "Swift": [],
    "Scala": [],
    "SQL": [],
    "Bash": ["Shell scripting", "shell script", "shell scripts"],
    "PowerShell": [],
    "MATLAB": [],
    "Dart": [],
    "Elixir": [],
    "Perl": [],
    "Objective-C": [],
    "Haskell": [],
    "Solidity": [],
    "HTML": ["HTML5"],
    "CSS": ["CSS3"],
    # frontend
    "React": ["React.js", "ReactJS", "React JS"],
    "Next.js": ["NextJS", "Next js"],
    "Angular": ["AngularJS"],
    "Vue": ["Vue.js", "VueJS"],
    "Svelte": [],
    "Redux": [],
    "Tailwind CSS": ["Tailwind", "TailwindCSS"],
    "Sass": ["SCSS"],
    "Webpack": [],
    "Vite": [],
    "jQuery": [],
    "React Native": [],
    "Flutter": [],
    # backend
    "Node.js": ["Node", "NodeJS", "Node JS"],
    "Express": ["Express.js", "ExpressJS"],
    "NestJS": [],
    "Django": [],
    "Flask": [],
    "FastAPI": [],
    "Spring": ["Spring Boot", "SpringBoot"],
    ".NET": ["dotnet", "ASP.NET", ".NET Core"],
    "Ruby on Rails": ["Rails"],
    "Laravel": [],
    "GraphQL": [],
    "REST": ["RESTful", "REST API", "REST APIs"],
    "gRPC": [],
    "Microservices": ["microservice", "micro-services"],
    "WebSockets": ["WebSocket"],
    # data stores
    "PostgreSQL": ["Postgres"],
    "MySQL": [],
    "SQL Server": ["MSSQL", "T-SQL"],
    "Oracle": [],
    "SQLite": [],
    "MongoDB": ["Mongo"],
    "Redis": [],
    "Cassandra": [],
    "DynamoDB": [],
    "Elasticsearch": ["Elastic Search", "OpenSearch"],
    "Snowflake": [],
    "BigQuery": [],
    "Redshift": [],
    "Databricks": [],
    "pgvector": [],
    "Pinecone": [],
    # data / ML
    "Spark": ["Apache Spark", "PySpark"],
    "Hadoop": [],
    "Kafka": ["Apache Kafka"],
    "RabbitMQ": [],
    "Message queues": ["message queue", "message broker", "SQS", "Pub/Sub", "event streaming"],
    "Celery": [],
    "Airflow": ["Apache Airflow"],
    "dbt": [],
    "ETL": ["ELT"],
    "Data pipelines": ["data pipeline"],
    "Data warehousing": ["data warehouse"],
    "Pandas": [],
    "NumPy": [],
    "scikit-learn": ["sklearn", "scikit learn"],
    "TensorFlow": [],
    "PyTorch": [],
    "Keras": [],
    "Machine learning": ["ML"],
    "Deep learning": [],
    "NLP": ["Natural language processing"],
    "Computer vision": [],
    "LLM": ["LLMs", "large language model", "large language models"],
    "Generative AI": ["GenAI", "Gen AI"],
    "RAG": ["retrieval augmented generation", "retrieval-augmented generation"],
    "LangChain": [],
    "LangGraph": [],
    "Hugging Face": ["HuggingFace", "Transformers"],
    "MLOps": [],
    "Statistics": ["statistical"],
    "A/B testing": ["AB testing", "A/B tests", "experimentation"],
    "Tableau": [],
    "Power BI": ["PowerBI"],
    "Looker": [],
    "Excel": ["Microsoft Excel", "spreadsheets"],
    "Data analysis": ["data analytics", "analytics"],
    "Data visualization": ["data visualisation", "dashboards"],
    # cloud / devops
    "AWS": ["Amazon Web Services"],
    "Azure": ["Microsoft Azure"],
    "GCP": ["Google Cloud", "Google Cloud Platform"],
    "Docker": ["containers", "containerization"],
    "Kubernetes": ["K8s", "EKS", "AKS", "GKE"],
    "Terraform": [],
    "Ansible": [],
    "CI/CD": ["CI CD", "continuous integration", "continuous delivery", "continuous deployment"],
    "GitHub Actions": [],
    "Jenkins": [],
    "GitLab CI": [],
    "Git": ["GitHub", "GitLab", "version control"],
    "Linux": ["Unix"],
    "Serverless": ["AWS Lambda", "Lambda", "Cloud Functions", "Azure Functions"],
    "Infrastructure as code": ["IaC"],
    "Observability": ["monitoring", "Prometheus", "Grafana", "Datadog"],
    "Nginx": [],
    "Postman": [],
    "Selenium": [],
    "Playwright": [],
    "Cypress": [],
    # practices
    "Unit testing": ["unit tests", "pytest", "Jest", "JUnit", "automated testing", "test automation"],
    "Agile": ["Scrum", "Kanban"],
    "System design": ["distributed systems", "scalable systems"],
    "Security": ["OWASP", "application security", "cybersecurity"],
    "OAuth": ["OAuth2", "OIDC", "SSO", "JWT"],
    "API design": [],
    "Code review": ["code reviews"],
    "Object-oriented programming": ["OOP", "object oriented"],
    "Data structures": ["algorithms"],
    "Performance optimization": ["performance tuning"],
    # tools / business
    "Jira": [],
    "Figma": [],
    "Salesforce": [],
    "SAP": [],
    "Product management": [],
    "Project management": ["PMP"],
    "Stakeholder management": ["stakeholders"],
    # soft skills
    "Communication": ["communicator", "written and verbal", "verbal and written"],
    "Leadership": ["led a team", "team lead", "mentoring", "mentored", "mentor"],
    "Collaboration": ["cross-functional", "cross functional", "teamwork"],
    "Problem solving": ["problem-solving"],
}

# Ordinary English words that are only a skill when written in their proper case.
CASE_SENSITIVE = {"Go", "Rust", "Swift", "Spring", "Express", "Node", "Rails", "Oracle", "Lambda", "Git", "ML", "TS", "JS", "Mongo"}


# Knowing the specific tool proves the general skill (PostgreSQL experience is SQL experience).
IMPLIED_BY: dict[str, list[str]] = {
    "SQL": ["PostgreSQL", "MySQL", "SQL Server", "SQLite", "Oracle", "BigQuery", "Snowflake", "Redshift"],
    "JavaScript": ["TypeScript", "React", "Angular", "Vue", "Node.js", "Next.js"],
    "Machine learning": ["scikit-learn", "TensorFlow", "PyTorch", "Keras", "Deep learning"],
    "Docker": ["Kubernetes"],
    "Message queues": ["Kafka", "RabbitMQ"],
    "Infrastructure as code": ["Terraform", "Ansible"],
    "CI/CD": ["GitHub Actions", "Jenkins", "GitLab CI"],
    "Data visualization": ["Tableau", "Power BI", "Looker"],
}


def _pattern(term: str) -> re.Pattern[str]:
    # Word boundaries that also respect symbols in names like C++, C#, .NET, Node.js and CI/CD.
    body = re.escape(term).replace(r"\ ", r"[\s-]+")
    flags = 0 if term in CASE_SENSITIVE else re.IGNORECASE
    return re.compile(rf"(?<![\w+#.]){body}(?![\w+#]|\.\w)", flags)


@lru_cache
def _compiled() -> list[tuple[str, list[re.Pattern[str]]]]:
    return [(name, [_pattern(t) for t in [name, *aliases]]) for name, aliases in SKILLS.items()]


def find_skills(text: str) -> list[str]:
    """Canonical skill names mentioned in `text`, in vocabulary order, without duplicates."""
    return [name for name, patterns in _compiled() if any(p.search(text) for p in patterns)]


def mentions(skill: str, text: str) -> bool:
    for name, patterns in _compiled():
        if name == skill:
            return any(p.search(text) for p in patterns)
    return False


def implied_by(skill: str, text: str) -> str | None:
    """The more specific skill in `text` that proves `skill`, if any."""
    return next((child for child in IMPLIED_BY.get(skill, []) if mentions(child, text)), None)


def resume_skills(text: str) -> set[str]:
    """Skills a resume shows, including the general skills its specific tools imply."""
    found = set(find_skills(text))
    return found | {parent for parent, children in IMPLIED_BY.items() if found & set(children)}
