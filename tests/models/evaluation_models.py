from pydantic import BaseModel


class ConversationEvaluation(BaseModel):
    tone_consistency: int       # 1-5: kawaii persona maintained throughout
    information_completeness: int  # 1-5: all incident details gathered
    flow_naturalness: int       # 1-5: conversation felt natural, well-guided
    personalization: int        # 1-5: used reporter's name, confirmed details
    overall_score: int          # 1-5: holistic quality
    rationale: str              # explanation of the grade
    passed: bool                # True if overall_score >= 3
