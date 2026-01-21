from pydantic import BaseModel
from typing import Literal
from datetime import date, datetime

class Incident(BaseModel):
    incident_type: str
    description: str
    date_of_occurrence: date | None
    location: str
    person_involved: str
    reporter_name: str | None
    serverity_level: int

class Feedback(BaseModel):
    topic: str
    summary: str
    sentiment: Literal["positive", "neutral", "negative"]

class Conversation(BaseModel):
    #Topics
    topics: list[str]
    primary_topic: str
    #Analytical Signals
    topic_shift_count: int
    turn_count: int

class Conversation(BaseModel):
    #Topics
    topics: list[str]
    primary_topic: str
    #Analytical Signals
    topic_shift_count: int
    turn_count: int
    # Interventions
    handoff_count: int 
    #Category
    conversation_type: Literal["incident","feedback","inquiry","other"]
    #Sentiments
    sentiment_start: float
    sentiment_end: float
    sentiment_trend: float #Quantitative
    sentiment_direction: Literal["up", "down", "flat"] #Qualitative
    #Outcome
    resolved: bool

    # To be added soon:
    # avg_response_time
    # message_count