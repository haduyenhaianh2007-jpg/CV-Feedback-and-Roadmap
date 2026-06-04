# document_understanding/cv_schema.py
from typing import Optional, List, Dict, Any

class BaseModel:
    def __init__(self, **data):
        for key, value in data.items():
            setattr(self, key, value)

    def dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

def Field(default_factory=None, **kwargs):
    return default_factory

def field_validator(*fields, mode='before'):
    def decorator(func):
        return func
    return decorator

# --- Các model ---
class PersonalInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None

class Education(BaseModel):
    school: Optional[str] = None
    degree: Optional[str] = None
    major: Optional[str] = None
    location: Optional[str] = None
    gpa: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    currently_studying: Optional[bool] = None
    description: List[str] = []

class Experience(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    currently_working: Optional[bool] = None
    description: List[str] = []
    location: Optional[str] = None

class Project(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    technologies: List[str] = []
    description: List[str] = []
    url: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class Skill(BaseModel):
    category: Optional[str] = None
    skills: List[str] = []

class Certification(BaseModel):
    name: Optional[str] = None
    issuer: Optional[str] = None
    date: Optional[str] = None

class Award(BaseModel):
    title: Optional[str] = None
    organization: Optional[str] = None
    date: Optional[str] = None

class Language(BaseModel):
    language: Optional[str] = None
    proficiency: Optional[str] = None

class CV(BaseModel):
    personal_info: Optional[PersonalInfo] = None
    summary: Optional[str] = None
    education: List[Education] = []
    experience: List[Experience] = []
    projects: List[Project] = []
    skills: List[Skill] = []
    certifications: List[Certification] = []
    awards: List[Award] = []
    languages: List[Language] = []

    @classmethod
    def model_validate(cls, data: Dict[str, Any]) -> "CV":
        """Validate and construct CV from dictionary, compatible with Pydantic-style API."""
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, got {type(data)}")

        # Map nested objects
        mapped = dict(data)
        if 'personal_info' in mapped and isinstance(mapped['personal_info'], dict):
            mapped['personal_info'] = PersonalInfo(**mapped['personal_info'])
        if 'education' in mapped:
            mapped['education'] = [Education(**e) if isinstance(e, dict) else e for e in mapped['education']]
        if 'experience' in mapped:
            mapped['experience'] = [Experience(**e) if isinstance(e, dict) else e for e in mapped['experience']]
        if 'projects' in mapped:
            mapped['projects'] = [Project(**p) if isinstance(p, dict) else p for p in mapped['projects']]
        if 'skills' in mapped:
            mapped['skills'] = [Skill(**s) if isinstance(s, dict) else s for s in mapped['skills']]
        if 'certifications' in mapped:
            mapped['certifications'] = [Certification(**c) if isinstance(c, dict) else c for c in mapped['certifications']]
        if 'awards' in mapped:
            mapped['awards'] = [Award(**a) if isinstance(a, dict) else a for a in mapped['awards']]
        if 'languages' in mapped:
            mapped['languages'] = [Language(**l) if isinstance(l, dict) else l for l in mapped['languages']]

        return cls(**mapped)

    def model_dump(self, exclude_none: bool = False) -> Dict[str, Any]:
        """Dump CV to dictionary, compatible with Pydantic-style API."""
        result = {}
        for key, value in self.__dict__.items():
            if key.startswith('_'):
                continue
            if isinstance(value, BaseModel):
                dumped = value.dict()
                if exclude_none:
                    dumped = {k: v for k, v in dumped.items() if v is not None}
                result[key] = dumped
            elif isinstance(value, list):
                dumped_list = []
                for item in value:
                    if isinstance(item, BaseModel):
                        d = item.dict()
                        if exclude_none:
                            d = {k: v for k, v in d.items() if v is not None}
                        dumped_list.append(d)
                    else:
                        if not exclude_none or item is not None:
                            dumped_list.append(item)
                result[key] = dumped_list
            else:
                if not exclude_none or value is not None:
                    result[key] = value
        return result