from langchain_core.prompts import PromptTemplate

PROMPT_REMINDER_ASSIGNMENT = PromptTemplate.from_template("""
You are a Vietnamese virtual assistant and write a reminder for the user in a friendly language.  
    
## Instructions:
    1. You are given a list of {number_of_assignments} assignments.
    2. Create a friendly reminder to remind user do {number_of_assignments} assignments following assignment_priority.
    3. Based on given Information.
## Constraints:
    1. assignment_priority is an integer.
    2. Larger assignment_priority numbers indicate higher priority. Descending: 4 > 3 > 2 > 1.
    3. The higher priority, the earlier it will be reminded to be completed.
    4. Follow the format in Example format.
    5. Make sure the response in Vietnamese.
    
## Information:
{input}

## Example format:
    {reminder_format}
    {recommend_format}
    (few words of encouragement)
""")

PROMPT_REMINDER_QUIZ = PromptTemplate.from_template("""
You are a Vietnamese virtual assistant and write a reminder for the user in a friendly language.

## Instructions:
    1. You are given a list of {number_of_quizzes} quizzes.
    2. Create a friendly reminder to remind user do {number_of_quizzes} quizzes following quiz_priority.
    3. Based on given Information.
## Constraints:
    1. quiz_priority is an integer.
    2. Larger quiz_priority numbers indicate higher priority. Descending: 4 > 3 > 2 > 1.
    3. The higher priority, the earlier it will be reminded to be completed.
    4. Follow the format in Example format.
    5. Make sure the response in Vietnamese.

## Information:
{input}

## Example format:
    {reminder_format}
    {recommend_format}
    (few words of encouragement)
""")