"""
Improvement Analyzer Module
Generates rule-based actionable improvement actions for missing skills.
"""
from typing import List, Dict


class ImprovementAnalyzer:
    """
    Rule-based improvement suggestions.
    Priority is derived from severity:
    - critical_gaps -> "High"
    - medium_gaps   -> "Medium"
    - optional_gaps -> "Low"

    Action templates are generic per-skill-category suggestions.
    LLM will later tailor these to the user's context.
    """

    # Generic action templates keyed by skill (canonical name).
    # Add more as needed; unknown skills fall back to a generic template.
    ACTION_TEMPLATES: Dict[str, List[str]] = {
        "Docker": [
            "Learn Docker fundamentals: images, containers, volumes, networks",
            "Containerize at least one existing project end-to-end"
        ],
        "Kubernetes": [
            "Learn Kubernetes architecture: pods, deployments, services",
            "Deploy a containerized app to a local Minikube cluster"
        ],
        "AWS": [
            "Complete AWS Cloud Practitioner Essentials",
            "Deploy a small project using S3 + EC2 + RDS"
        ],
        "Azure": [
            "Complete Azure Fundamentals (AZ-900) learning path",
            "Deploy a small project using App Service + Azure SQL"
        ],
        "Google Cloud Platform": [
            "Complete Google Cloud Fundamentals",
            "Deploy a project using Cloud Run + Cloud SQL"
        ],
        "RAG": [
            "Learn vector databases (Chroma, FAISS, Pinecone)",
            "Build a simple RAG chatbot over a PDF corpus"
        ],
        "LLM": [
            "Study transformer architecture and attention mechanisms",
            "Fine-tune a small LLM (e.g. Llama) on a domain dataset"
        ],
        "PyTorch": [
            "Complete PyTorch official tutorials (tensors, autograd, nn)",
            "Train an image classifier from scratch on CIFAR-10"
        ],
        "TensorFlow": [
            "Complete TensorFlow/Keras official tutorials",
            "Build and train an image classifier end-to-end"
        ],
        "Machine Learning": [
            "Master scikit-learn for classical ML algorithms",
            "Complete an end-to-end ML project: EDA -> training -> evaluation"
        ],
        "Deep Learning": [
            "Study CNN and RNN architectures",
            "Reproduce a classic deep learning paper"
        ],
        "Computer Vision": [
            "Study OpenCV and image processing pipelines",
            "Build an object detection project using YOLO or Detectron2"
        ],
        "Natural Language Processing": [
            "Study tokenization, embeddings, and transformer models",
            "Build a text classification project using Hugging Face"
        ],
        "MLOps": [
            "Learn MLflow or Weights & Biases for experiment tracking",
            "Set up a CI/CD pipeline for an ML project"
        ],
        "CI/CD": [
            "Learn GitHub Actions or GitLab CI fundamentals",
            "Automate test + deploy pipeline for one project"
        ],
        "Apache Spark": [
            "Learn Spark RDDs, DataFrames, and Spark SQL",
            "Process a large dataset (>10GB) using PySpark"
        ],
        "Prompt Engineering": [
            "Study prompt patterns: zero-shot, few-shot, chain-of-thought",
            "Build a prompt library for a real use case"
        ],
        "Fine-tuning": [
            "Study LoRA, QLoRA, and PEFT techniques",
            "Fine-tune a pre-trained model on a custom dataset"
        ],
        "Git": [
            "Master branching, rebasing, and merge strategies",
            "Contribute to an open-source project via pull requests"
        ],
        "SQL": [
            "Practice advanced SQL: window functions, CTEs, optimization",
            "Solve 50+ SQL problems on LeetCode/HackerRank"
        ],
        "Python": [
            "Deepen Python knowledge: async, decorators, metaclasses",
            "Build a production-quality Python package"
        ]
    }

    # Fallback template when skill is not in ACTION_TEMPLATES
    GENERIC_TEMPLATE = [
        "Study core concepts and official documentation",
        "Build a small hands-on project demonstrating the skill"
    ]

    def analyze(
        self,
        critical_gaps: List[Dict],
        medium_gaps: List[Dict],
        optional_gaps: List[Dict] = None,
        max_actions: int = 5
    ) -> Dict:
        """
        Args:
            critical_gaps, medium_gaps, optional_gaps: lists from SeverityAnalyzer
            max_actions: cap on total actions returned (keep output concise)

        Returns:
            {
                "improvement_actions": [
                    {
                        "skill": "Docker",
                        "priority": "High",
                        "frequency": 81,
                        "reason": "Appears in 81% of AI Engineer jobs",
                        "actions": ["...", "..."]
                    },
                    ...
                ]
            }
        """
        actions = []

        priority_groups = [
            (critical_gaps, "High"),
            (medium_gaps, "Medium"),
            (optional_gaps or [], "Low")
        ]

        for gaps, priority in priority_groups:
            for gap in gaps:
                skill = gap["skill"]
                freq = gap["frequency"]

                actions.append({
                    "skill": skill,
                    "priority": priority,
                    "frequency": freq,
                    "reason": f"Appears in {freq:.0f}% of target role job descriptions",
                    "actions": self.ACTION_TEMPLATES.get(skill, self.GENERIC_TEMPLATE)
                })

                if len(actions) >= max_actions:
                    break

            if len(actions) >= max_actions:
                break

        return {"improvement_actions": actions}
