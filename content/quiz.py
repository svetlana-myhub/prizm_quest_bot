from content.facts import FACTS

QUIZ_BY_FACT_ID = {
    fact["id"]: fact["quiz"]
    for fact in FACTS
}