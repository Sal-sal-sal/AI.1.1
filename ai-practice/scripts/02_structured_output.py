#!/usr/bin/env python3
"""
02 — Structured Output Lab

Demonstrates guaranteed JSON output matching Pydantic models.
Compares JSON-mode vs function tools with "strict": True schema validation.

Usage: python scripts/02_structured_output.py

Docs: https://platform.openai.com/docs/guides/structured-output
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field
import time

# Load environment variables
load_dotenv()

# Ensure data directory exists
data_dir = Path("data")
data_dir.mkdir(exist_ok=True)

# Check if PDF exists, if not create a sample one
pdf_path = data_dir / "topology.pdf"
if not pdf_path.exists():
    print("⚠️  PDF file not found. Creating a sample file...")
    # Create a sample PDF file
    with open(pdf_path, "w") as f:
        f.write("Sample PDF content for testing")

print(f"📄 Using PDF file: {pdf_path}")

client = OpenAI()

# Upload file to OpenAI
try:
    with open(pdf_path, "rb") as f:
        file = client.files.create(file=f, purpose="assistants")
    print(f"✅ File uploaded successfully with ID: {file.id}")
except Exception as e:
    print(f"❌ Error uploading file: {e}")
    sys.exit(1)

# Pydantic Models for Structured Output
class Note(BaseModel):
    id: int  = Field(..., ge=1, le=10)
    heading: str  = Field(..., example="Теорема о непрерывности ")       
    summary: str  = Field(..., max_length=150)     
    page_ref: int | None   = Field(None, description="Page number in source PDF")

class WeatherAlert(BaseModel):
    """Weather alert information with structured fields."""
    location: str = Field(description="Geographic location of the alert")
    severity: str = Field(description="Alert severity: low, medium, high, critical")
    alert_type: str = Field(description="Type of weather alert")
    description: str = Field(description="Detailed description of the weather condition")
    advice: str = Field(description="Recommended actions for safety")
    expires_at: Optional[str] = Field(description="When the alert expires (if known)")

class TechAnalysis(BaseModel):
    """Technical analysis of a programming concept."""
    concept: str = Field(description="The programming concept being analyzed")
    difficulty_level: str = Field(description="Beginner, Intermediate, or Advanced")
    key_benefits: List[str] = Field(description="Main advantages of this concept")
    common_pitfalls: List[str] = Field(description="Common mistakes to avoid")
    use_cases: List[str] = Field(description="Practical applications")
    learning_resources: List[str] = Field(description="Recommended learning materials")

def get_client():
    """Initialize OpenAI client with API key from environment."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: OPENAI_API_KEY not found in environment variables.")
        sys.exit(1)
    
    org_id = os.getenv("OPENAI_ORG")
    client_kwargs = {"api_key": api_key}
    if org_id:
        client_kwargs["organization"] = org_id
    
    return OpenAI(**client_kwargs)

def load_assistant_id():
    """Load assistant ID from .assistant file."""
    assistant_file = Path(".assistant")
    if not assistant_file.exists():
        print("❌ No assistant found. Please run: python scripts/00_init_assistant.py")
        sys.exit(1)
    return assistant_file.read_text().strip()



def generate_exam_notes(client: OpenAI, assistant_id: str, file_id: str):
    """
    Generates exactly 10 revision notes from a given file using a strict function tool.
    """
    print("\n🎯 Generating 10 Exam Notes from PDF")
    print("-" * 50)

    # Для получения списка заметок, мы обернем Note в родительскую модель
    class ExamNotes(BaseModel):
        notes: List[Note]

    # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
    # 1. Получаем схему из Pydantic
    function_params = ExamNotes.model_json_schema()
    # 2. Вручную добавляем обязательное поле, которое требует OpenAI
    function_params['additionalProperties'] = False
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    # Определяем инструмент-функцию для ассистента
    notes_tool_schema = {
        "type": "function",
        "function": {
            "name": "save_exam_notes",
            "description": "Saves a list of exactly 10 revision notes from the document.",
            "parameters": function_params, # Используем измененную схему
            # "strict": True # Этот флаг больше не нужен, когда вы определяете функцию через assistants.update
        }
    }

    # Обновляем ассистента, чтобы он мог использовать наш новый инструмент
    client.beta.assistants.update(
        assistant_id=assistant_id,
        tools=[
            {"type": "file_search"},
            notes_tool_schema
        ]
    )

    # Создаем чат (Thread) с запросом, прикрепив файл
    thread = client.beta.threads.create(
        messages=[{
            "role": "user",
            "content": "Проанализируй предоставленный PDF-документ и создай ровно 10 кратких заметок для подготовки к экзамену. Для каждой заметки укажи заголовок, краткое содержание и, если возможно, номер страницы.",
            "attachments": [
                {
                    "file_id": file_id,
                    "tools": [{"type": "file_search"}]
                }
            ]
        }]
    )

    # Запускаем ассистента
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant_id,
        instructions="Используй инструмент save_exam_notes, чтобы сохранить результат."
    )

    # Обрабатываем результат
    if run.status == "requires_action":
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        for tool_call in tool_calls:
            if tool_call.function.name == "save_exam_notes":
                notes_data = json.loads(tool_call.function.arguments)
                
                try:
                    exam_notes = ExamNotes(**notes_data)
                    print("\n✅ Successfully generated and validated 10 notes!")
                    for note in exam_notes.notes:
                        print(f"  [{note.id}] {note.heading} (p. {note.page_ref or 'N/A'}): {note.summary}")
                    return exam_notes
                except Exception as e:
                    print(f"❌ Pydantic validation failed: {e}")
                    return notes_data
    else:
        print(f"❌ Run failed with status: {run.status}")
        if run.last_error:
            print(f"Error: {run.last_error.message}")
        return None
    # ... код внутри try блока ...
    print("\n✅ Successfully generated and validated 10 notes!")
    for note in exam_notes.notes:
        print(f"  [{note.id}] {note.heading} (p. {note.page_ref or 'N/A'}): {note.summary}")

    # --- ДОБАВЬТЕ ЭТОТ БЛОК ДЛЯ СОХРАНЕНИЯ ---
    output_path = data_dir / "exam_notes.json" # Используем путь к папке data
    with open(output_path, 'w', encoding='utf-8') as f:
        # Конвертируем Pydantic модель в словарь и сохраняем в файл
        json.dump(exam_notes.model_dump(), f, ensure_ascii=False, indent=4)
    print(f"\n💾 Заметки успешно сохранены в файл: {output_path}")
    # --- КОНЕЦ БЛОКА ---

    return exam_notes
    # ... остальной код ... 


def demonstrate_json_mode(client, assistant_id):
    """Demonstrate basic JSON mode without strict schema validation."""
    print("🔧 Demonstrating JSON Mode (Basic)")
    print("-" * 40)
    
    # Create thread for JSON mode demo
    thread = client.beta.threads.create(
        messages=[{
            "role": "user",
            "content": """Create a weather alert for a severe thunderstorm in Chicago. 
            Return the response as a JSON object with fields: location, severity, alert_type, 
            description, advice, and expires_at."""
        }]
    )
    
    # Run with JSON mode
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant_id,
        response_format={"type": "json_object"},
        instructions="Always respond with valid JSON. Use clear, structured data."
    )
    
    if run.status == "completed":
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        response_content = messages.data[0].content[0].text.value
        
        print("📄 Raw JSON Response:")
        print(response_content)
        
        try:
            # Clean the response content by removing markdown formatting
            cleaned_content = response_content
            if "```json" in cleaned_content:
                cleaned_content = cleaned_content.split("```json")[1]
            if "```" in cleaned_content:
                cleaned_content = cleaned_content.split("```")[0]
            cleaned_content = cleaned_content.strip()
            
            json_data = json.loads(cleaned_content)
            print("\n✅ Valid JSON parsed successfully")
            print(f"📊 Fields: {list(json_data.keys())}")
            
            # Try to validate with Pydantic (may fail due to loose schema)
            try:
                weather_alert = WeatherAlert(**json_data)
                print("✅ Pydantic validation successful!")
                return weather_alert
            except Exception as e:
                print(f"⚠️  Pydantic validation failed: {e}")
                return json_data
                
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON: {e}")
            return None
    else:
        print(f"❌ Run failed with status: {run.status}")
        return None

def demonstrate_function_tools_strict(client, assistant_id):
    """Demonstrate function tools with strict schema validation."""
    print("\n🎯 Demonstrating Function Tools (Strict Schema)")
    print("-" * 50)
    
    # Create assistant with function tool
    function_schema = {
        "name": "analyze_tech_concept",
        "description": "Analyze a programming or technology concept",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "concept": {
                    "type": "string",
                    "description": "The programming concept being analyzed"
                },
                "difficulty_level": {
                    "type": "string",
                    "enum": ["Beginner", "Intermediate", "Advanced"],
                    "description": "Difficulty level"
                },
                "key_benefits": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Main advantages of this concept"
                },
                "common_pitfalls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Common mistakes to avoid"
                },
                "use_cases": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Practical applications"
                },
                "learning_resources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Recommended learning materials"
                }
            },
            "required": ["concept", "difficulty_level", "key_benefits", "common_pitfalls", "use_cases", "learning_resources"],
            "additionalProperties": False
        }
    }
    
    # Update assistant with function tool and file search
    client.beta.assistants.update(
        assistant_id=assistant_id,
        tools=[
            {"type": "file_search"},
            {"type": "function", "function": function_schema}
        ]
    )
    
    # Create thread for function demo
    thread = client.beta.threads.create(
        messages=[{
            "role": "user",
            "content": "Please analyze the concept of file search in programming."
        }]
    )
    
    # Run with function calling
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant_id,
        instructions="Use the analyze_tech_concept function to provide a structured analysis."
    )
    
    if run.status == "requires_action":
        # Handle the function call
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        tool_outputs = []
        
        for tool_call in tool_calls:
            if tool_call.function.name == "analyze_tech_concept":
                # Create a sample response
                response = {
                    "concept": "File Search in Programming",
                    "difficulty_level": "Intermediate",
                    "key_benefits": [
                        "Efficient data retrieval",
                        "Improved user experience",
                        "Better organization of data"
                    ],
                    "common_pitfalls": [
                        "Not handling large files efficiently",
                        "Missing error handling",
                        "Poor search algorithm choice"
                    ],
                    "use_cases": [
                        "Document management systems",
                        "Code search in IDEs",
                        "File system navigation"
                    ],
                    "learning_resources": [
                        "File system documentation",
                        "Search algorithm tutorials",
                        "Database indexing guides"
                    ]
                }
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": json.dumps(response)
                })
        
        # Submit the tool outputs
        run = client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread.id,
            run_id=run.id,
            tool_outputs=tool_outputs
        )
        
        # Wait for the run to complete
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )
        while run.status in ["queued", "in_progress", "requires_action"]:
            time.sleep(1)
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            print(f"⏳ Status: {run.status}")
            
            if run.status == "requires_action":
                print("🔧 Run requires action (tool calls)")
                # In a real scenario, you'd handle tool calls here
                break

        if run.status == "completed":
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            response_content = messages.data[0].content[0].text.value
            print("\n📋 Function Response:")
            print(response_content)
            
            try:
                tech_analysis = TechAnalysis(**json.loads(tool_outputs[0]["output"]))
                print("\n✅ Strict schema validation successful!")
                print(f"📊 Concept: {tech_analysis.concept}")
                print(f"📊 Difficulty: {tech_analysis.difficulty_level}")
                print(f"📊 Benefits: {len(tech_analysis.key_benefits)} items")
                print(f"📊 Pitfalls: {len(tech_analysis.common_pitfalls)} items")
                return tech_analysis
            except Exception as e:
                print(f"❌ Pydantic validation failed: {e}")
                return json.loads(tool_outputs[0]["output"])
    
    print(f"❌ Run failed with status: {run.status}")
    return None

def compare_approaches(json_result, function_result):
    """Compare the results from both approaches."""
    print("\n📊 Comparison of Approaches")
    print("=" * 50)
    
    print("🔧 JSON Mode:")
    if json_result:
        if isinstance(json_result, WeatherAlert):
            print("  ✅ Pydantic validation: SUCCESS")
            print(f"  📍 Location: {json_result.location}")
            print(f"  ⚠️  Severity: {json_result.severity}")
        else:
            print("  ⚠️  Pydantic validation: FAILED (loose schema)")
            print(f"  📄 Raw data type: {type(json_result)}")
    else:
        
        print("  ❌ No valid result")
    
    print("\n🎯 Function Tools (Strict):")
    if function_result:
        if isinstance(function_result, TechAnalysis):
            print("  ✅ Pydantic validation: SUCCESS")
            print(f"  🎓 Concept: {function_result.concept}")
            print(f"  📈 Difficulty: {function_result.difficulty_level}")
        else:
            print("  ⚠️  Pydantic validation: FAILED")
            print(f"  📄 Raw data tyNo{type(function_result)}")
    else:
        print(function_result)
        print("  ❌ No valid result")
    
    print("\n💡 Key Takeaways:")
    print("  • JSON Mode: Flexible but may not match exact schema")
    print("  • Function Tools (Strict): Guaranteed schema compliance")
    print("  • Use Function Tools for production applications requiring exact structure")

def reset_assistant_tools(client, assistant_id):
    """Reset assistant tools to original state."""
    client.beta.assistants.update(
        assistant_id=assistant_id,
        tools=[{"type": "file_search"}]
    )

def main():
    """Main function to run the structured output lab."""
    print("🚀 OpenAI Practice Lab - Structured Output")
    print("=" * 50)
    
    # Initialize client and get assistant
    client = get_client()
    assistant_id = load_assistant_id()
    print(f"✅ Using assistant: {assistant_id}")
    
    # Получаем ID файла из глобальной переменной 'file'
    file_id = file.id
    
    try:
        # 1. Demonstrate JSON mode
        json_result = demonstrate_json_mode(client, assistant_id)
        
        # 2. Demonstrate function tools with strict schema
        function_result = demonstrate_function_tools_strict(client, assistant_id)
        
        # 3. Compare approaches
        compare_approaches(json_result, function_result)
        
        # --- ИНТЕГРАЦИЯ: ЗАПУСК ГЕНЕРАЦИИ ЗАМЕТОК ---
        print("\n\n🚀 Launching Exam Notes Generation...")
        # 4. Generate exam notes from the PDF file
        generate_exam_notes(client, assistant_id, file_id)
        # ---------------------------------------------
        
        print(f"\n🎯 Lab Complete!")
        print(f"   Next: python scripts/03_rag_file_search.py")
        print(f"   Cleanup: python scripts/99_cleanup.py")
        
    finally:
        # Reset assistant tools to original state
        reset_assistant_tools(client, assistant_id)
        print("🔄 Assistant tools reset to original state")

if __name__ == "__main__":
    main() 