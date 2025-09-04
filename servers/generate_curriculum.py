from mcp.server.fastmcp import FastMCP
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import re
from urllib.parse import quote
import os
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

mcp = FastMCP(
    "CurriculumGenerator",
    instructions="You are an intelligent curriculum generator that creates personalized learning paths based on user goals and web research. You can search for learning resources, generate structured curriculums, and create daily study plans using advanced AI capabilities.",
    host="0.0.0.0",
    port=8006,
)

# Initialize LLM - agent.py와 동일한 방식으로 Ollama 사용
try:
    # Primary: Ollama (더 일반적인 모델 사용)
    ollama_llm = ChatOpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama", 
        model="midm-2.0-fp16:base",  # 실제 설치된 모델 사용
        temperature=0.7,
        max_tokens=2000,
    )
    llm_available = True
    print("Ollama LLM initialized (using midm-2.0-fp16:base)")
except Exception as e:
    print(f"Ollama LLM initialization failed: {e}")
    ollama_llm = None
    llm_available = False

class CurriculumDatabase:
    """Enhanced database with file persistence"""
    def __init__(self, data_dir: str = "data"):
        self.curriculums = {}
        self.daily_plans = {}
        self.learning_progress = {}
        self.data_dir = data_dir
        
        # Create data directory if it doesn't exist
        import os
        os.makedirs(data_dir, exist_ok=True)
        
        # Load existing data
        self._load_data()
    
    def _load_data(self):
        """Load data from JSON files"""
        try:
            curricula_file = os.path.join(self.data_dir, "curriculums.json")
            if os.path.exists(curricula_file):
                with open(curricula_file, 'r', encoding='utf-8') as f:
                    self.curriculums = json.load(f)
                print(f"Loaded {len(self.curriculums)} curriculum users from file")
            
            plans_file = os.path.join(self.data_dir, "daily_plans.json")
            if os.path.exists(plans_file):
                with open(plans_file, 'r', encoding='utf-8') as f:
                    self.daily_plans = json.load(f)
                print(f"Loaded {len(self.daily_plans)} daily plans from file")
            
            progress_file = os.path.join(self.data_dir, "progress.json")
            if os.path.exists(progress_file):
                with open(progress_file, 'r', encoding='utf-8') as f:
                    self.learning_progress = json.load(f)
                print(f"Loaded {len(self.learning_progress)} progress records from file")
        except Exception as e:
            print(f"Error loading data: {e}")
    
    def _save_data(self):
        """Save data to JSON files"""
        try:
            curricula_file = os.path.join(self.data_dir, "curriculums.json")
            with open(curricula_file, 'w', encoding='utf-8') as f:
                json.dump(self.curriculums, f, indent=2, ensure_ascii=False)
            
            plans_file = os.path.join(self.data_dir, "daily_plans.json")
            with open(plans_file, 'w', encoding='utf-8') as f:
                json.dump(self.daily_plans, f, indent=2, ensure_ascii=False)
            
            progress_file = os.path.join(self.data_dir, "progress.json")
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.learning_progress, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error saving data: {e}")
    
    def save_curriculum(self, user_id: str, curriculum: Dict):
        """Save curriculum for a user"""
        if user_id not in self.curriculums:
            self.curriculums[user_id] = []
        curriculum['id'] = len(self.curriculums[user_id])
        curriculum['created_at'] = datetime.now().isoformat()
        self.curriculums[user_id].append(curriculum)
        self._save_data()  # Auto-save to file
        return curriculum['id']
    
    def get_curriculum(self, user_id: str, curriculum_id: int) -> Optional[Dict]:
        """Get specific curriculum"""
        if user_id in self.curriculums and curriculum_id < len(self.curriculums[user_id]):
            return self.curriculums[user_id][curriculum_id]
        return None
    
    def save_daily_plan(self, user_id: str, curriculum_id: int, plan: Dict):
        """Save daily learning plan"""
        key = f"{user_id}_{curriculum_id}"
        if key not in self.daily_plans:
            self.daily_plans[key] = []
        self.daily_plans[key].append(plan)
        self._save_data()  # Auto-save to file
    
    def get_daily_plans(self, user_id: str, curriculum_id: int) -> List[Dict]:
        """Get all daily plans for a curriculum"""
        key = f"{user_id}_{curriculum_id}"
        return self.daily_plans.get(key, [])
    
    def update_progress(self, user_id: str, curriculum_id: int, day: int, progress: Dict):
        """Update learning progress"""
        key = f"{user_id}_{curriculum_id}_{day}"
        self.learning_progress[key] = progress
        self._save_data()  # Auto-save to file

db = CurriculumDatabase()

async def analyze_with_llm(prompt: str, context: Dict[str, Any] = None) -> str:
    """
    Use LLM to analyze and generate intelligent responses using Ollama
    """
    if not llm_available or not ollama_llm:
        return "LLM not available - using rule-based generation"

    try:
        # Build system message (agent.py와 동일한 패턴)
        system_message = """You are an expert educational curriculum designer with deep knowledge in:
- Learning science and pedagogy
- Skill progression and competency frameworks
- Personalized learning paths
- Educational resource evaluation

Provide detailed, actionable, and well-structured responses."""
        
        # Build user message
        user_prompt = prompt
        if context:
            context_str = f"\n\nContext information:\n{json.dumps(context, indent=2)}"
            user_prompt += context_str

        # Create message objects for ChatOpenAI
        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_prompt)
        ]
        
        # Call Ollama LLM (agent.py와 동일한 방식)
        print("Using Ollama LLM for analysis...")
        response = await ollama_llm.agenerate([messages])
        
        # Extract response content
        if response.generations and response.generations[0]:
            return response.generations[0][0].text
        else:
            return "No response generated from LLM"
            
    except Exception as e:
        print(f"Ollama LLM analysis failed: {e}")
        return "LLM analysis failed - using fallback methods"

async def generate_intelligent_curriculum_with_llm(
    topic: str,
    level: str,
    duration_weeks: int,
    focus_areas: List[str],
    user_context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Generate an intelligent curriculum using LLM
    """
    prompt = f"""Create a detailed {duration_weeks}-week curriculum for learning {topic} at {level} level.
    
    Focus areas: {', '.join(focus_areas) if focus_areas else 'General coverage'}
    
    Please provide a structured curriculum with:
    1. Clear weekly modules with specific topics
    2. Learning objectives for each module (3-5 objectives)
    3. Recommended study hours per module
    4. Key concepts to master
    5. Practical projects or exercises
    6. Prerequisites for each module
    7. Assessment criteria
    
    Format the response as a valid JSON object with this structure:
    {{
        "modules": [
            {{
                "week": 1,
                "title": "Module Title",
                "description": "Brief description",
                "objectives": ["objective1", "objective2"],
                "key_concepts": ["concept1", "concept2"],
                "estimated_hours": 10,
                "prerequisites": ["prerequisite1"],
                "projects": ["project description"],
                "assessment": "How to assess learning"
            }}
        ],
        "overall_goal": "What the learner will achieve",
        "recommended_pace": "Suggested learning pace",
        "additional_resources": ["Resource recommendations"]
    }}
    """
    
    llm_response = await analyze_with_llm(prompt, user_context)
    
    try:
        # Try to parse LLM response as JSON
        # Extract JSON from the response if it contains other text
        json_match = re.search(r'\{[\s\S]*\}', llm_response)
        if json_match:
            curriculum_data = json.loads(json_match.group())
            return curriculum_data
    except json.JSONDecodeError:
        print("Failed to parse LLM response as JSON, using structured extraction")
    
    # Fallback to structured extraction from text
    return extract_curriculum_from_text(llm_response, topic, duration_weeks)

def extract_curriculum_from_text(text: str, topic: str, duration_weeks: int) -> Dict[str, Any]:
    """
    Extract curriculum structure from unstructured text
    """
    modules = []
    
    # Try to extract weekly modules
    week_patterns = [
        r'Week\s+(\d+)[:\s-]*(.*?)(?=Week\s+\d+|$)',
        r'Module\s+(\d+)[:\s-]*(.*?)(?=Module\s+\d+|$)',
    ]
    
    for pattern in week_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
        for match in matches:
            week_num = int(match.group(1))
            content = match.group(2).strip()
            
            # Extract title (first line)
            lines = content.split('\n')
            title = lines[0].strip() if lines else f"Week {week_num}"
            
            modules.append({
                "week": week_num,
                "title": title,
                "description": content[:200],
                "objectives": extract_bullet_points(content, "objective"),
                "key_concepts": extract_bullet_points(content, "concept"),
                "estimated_hours": 10 + (week_num - 1) * 2,
                "prerequisites": [],
                "projects": extract_bullet_points(content, "project"),
                "assessment": "Complete exercises and project"
            })
            
            if len(modules) >= duration_weeks:
                break
        
        if modules:
            break
    
    # If no modules found, create default structure
    if not modules:
        for i in range(1, duration_weeks + 1):
            modules.append({
                "week": i,
                "title": f"{topic} - Week {i}",
                "description": f"Week {i} content for {topic}",
                "objectives": [f"Learn week {i} concepts", "Complete exercises"],
                "key_concepts": [],
                "estimated_hours": 10 + (i - 1) * 2,
                "prerequisites": [f"Week {i-1} completion"] if i > 1 else [],
                "projects": ["Weekly project"],
                "assessment": "Complete weekly assessment"
            })
    
    return {
        "modules": modules,
        "overall_goal": f"Master {topic} in {duration_weeks} weeks",
        "recommended_pace": "Follow weekly schedule",
        "additional_resources": []
    }

def extract_bullet_points(text: str, keyword: str) -> List[str]:
    """
    Extract bullet points related to a keyword from text
    """
    points = []
    patterns = [
        r'[-•*]\s*(.*?' + keyword + r'.*?)(?=[-•*\n]|$)',
        r'\d+\.\s*(.*?' + keyword + r'.*?)(?=\d+\.|$)',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            point = match.group(1).strip()
            if point and len(point) < 200:
                points.append(point)
    
    return points[:5]  # Limit to 5 points

async def search_duckduckgo(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """
    Search DuckDuckGo for learning resources
    """
    try:
        encoded_query = quote(query)
        url = f"https://duckduckgo.com/html/?q={encoded_query}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                content = response.text
                
                # Simple HTML parsing for results
                results = []
                result_pattern = r'<a class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
                snippet_pattern = r'<a class="result__snippet"[^>]*>(.*?)</a>'
                
                matches = re.finditer(result_pattern, content)
                snippets = re.finditer(snippet_pattern, content)
                
                snippet_list = [s.group(1).strip() for s in snippets]
                
                for i, match in enumerate(matches):
                    if i >= num_results:
                        break
                    
                    url = match.group(1)
                    title = re.sub(r'<[^>]+>', '', match.group(2))
                    snippet = snippet_list[i] if i < len(snippet_list) else ""
                    
                    results.append({
                        "title": title.strip(),
                        "url": url,
                        "snippet": re.sub(r'<[^>]+>', '', snippet).strip()
                    })
                
                return results
            
            # Fallback to using lite.duckduckgo.com API endpoint
            api_url = f"https://lite.duckduckgo.com/lite/?q={encoded_query}"
            response = await client.get(api_url, timeout=10.0)
            
            if response.status_code == 200:
                # Parse lite version HTML
                content = response.text
                results = []
                
                # Extract links from lite version
                link_pattern = r'<a[^>]*class="result-link"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
                for match in re.finditer(link_pattern, content):
                    if len(results) >= num_results:
                        break
                    results.append({
                        "title": re.sub(r'<[^>]+>', '', match.group(2)).strip(),
                        "url": match.group(1),
                        "snippet": ""
                    })
                
                return results
                
    except Exception as e:
        print(f"Error searching DuckDuckGo: {e}")
        
    # Return empty list if search fails
    return []

def analyze_learning_resources(search_results: List[Dict], topic: str) -> Dict[str, Any]:
    """
    Analyze search results to extract learning resources
    """
    resources = {
        "tutorials": [],
        "documentation": [],
        "videos": [],
        "courses": [],
        "articles": [],
        "tools": []
    }
    
    for result in search_results:
        title_lower = result['title'].lower()
        url = result['url'].lower()
        
        # Categorize resources
        if any(word in title_lower for word in ['tutorial', 'guide', 'how to', 'learn']):
            resources['tutorials'].append(result)
        elif any(word in url for word in ['docs', 'documentation', 'reference']):
            resources['documentation'].append(result)
        elif 'youtube' in url or 'video' in title_lower:
            resources['videos'].append(result)
        elif any(word in url for word in ['coursera', 'udemy', 'edx', 'course']):
            resources['courses'].append(result)
        elif any(word in title_lower for word in ['article', 'blog', 'post']):
            resources['articles'].append(result)
        else:
            resources['tools'].append(result)
    
    return resources

def generate_curriculum_structure(
    topic: str, 
    level: str, 
    duration_weeks: int, 
    resources: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate structured curriculum based on topic and resources
    """
    curriculum = {
        "title": f"{topic} Learning Path",
        "level": level,
        "duration_weeks": duration_weeks,
        "modules": []
    }
    
    # Define module structure based on level
    if level == "beginner":
        module_structure = [
            {"week": 1, "title": f"Introduction to {topic}", "focus": "fundamentals"},
            {"week": 2, "title": "Basic Concepts", "focus": "core_concepts"},
            {"week": 3, "title": "Hands-on Practice", "focus": "practical"},
            {"week": 4, "title": "Building Projects", "focus": "projects"}
        ]
    elif level == "intermediate":
        module_structure = [
            {"week": 1, "title": "Advanced Concepts", "focus": "advanced"},
            {"week": 2, "title": "Best Practices", "focus": "patterns"},
            {"week": 3, "title": "Real-world Applications", "focus": "applications"},
            {"week": 4, "title": "Complex Projects", "focus": "projects"}
        ]
    else:  # advanced
        module_structure = [
            {"week": 1, "title": "Expert Techniques", "focus": "expert"},
            {"week": 2, "title": "Architecture & Design", "focus": "architecture"},
            {"week": 3, "title": "Performance & Optimization", "focus": "optimization"},
            {"week": 4, "title": "Industry-level Projects", "focus": "professional"}
        ]
    
    # Adjust for requested duration
    total_modules = min(duration_weeks, len(module_structure) * 3)
    
    for i in range(total_modules):
        module_idx = i % len(module_structure)
        module_template = module_structure[module_idx]
        
        module = {
            "week": i + 1,
            "title": f"{module_template['title']} - Part {(i // len(module_structure)) + 1}" if i >= len(module_structure) else module_template['title'],
            "objectives": [
                f"Understand key concepts of {module_template['focus']}",
                f"Apply {topic} in {module_template['focus']} context",
                f"Complete practical exercises"
            ],
            "resources": {
                "primary": resources.get('tutorials', [])[:2] if module_template['focus'] in ['fundamentals', 'core_concepts'] else resources.get('documentation', [])[:2],
                "supplementary": resources.get('articles', [])[:2],
                "practice": resources.get('videos', [])[:1]
            },
            "estimated_hours": 10 + (i * 2)  # Progressive difficulty
        }
        curriculum["modules"].append(module)
    
    # Add recommended resources
    curriculum["recommended_resources"] = {
        "courses": resources.get('courses', [])[:3],
        "documentation": resources.get('documentation', [])[:3],
        "tools": resources.get('tools', [])[:3]
    }
    
    return curriculum

def create_daily_study_plan(module: Dict, days_per_week: int = 5) -> List[Dict[str, Any]]:
    """
    Create daily study plan for a module
    """
    daily_plans = []
    hours_per_day = module["estimated_hours"] / days_per_week
    
    day_types = [
        {"type": "concept", "focus": "Learning new concepts", "percentage": 0.3},
        {"type": "practice", "focus": "Hands-on practice", "percentage": 0.4},
        {"type": "review", "focus": "Review and consolidation", "percentage": 0.2},
        {"type": "project", "focus": "Project work", "percentage": 0.1}
    ]
    
    for day in range(1, days_per_week + 1):
        day_type = day_types[(day - 1) % len(day_types)]
        
        plan = {
            "day": day,
            "date": (datetime.now() + timedelta(days=day-1)).strftime("%Y-%m-%d"),
            "type": day_type["type"],
            "focus": day_type["focus"],
            "duration_hours": round(hours_per_day * (1 + day_type["percentage"]), 1),
            "tasks": []
        }
        
        # Add specific tasks based on day type
        if day_type["type"] == "concept":
            plan["tasks"] = [
                {"task": "Read primary resources", "duration": "45 min", "completed": False},
                {"task": "Take notes on key concepts", "duration": "30 min", "completed": False},
                {"task": "Watch explanatory videos", "duration": "30 min", "completed": False}
            ]
        elif day_type["type"] == "practice":
            plan["tasks"] = [
                {"task": "Complete coding exercises", "duration": "60 min", "completed": False},
                {"task": "Solve practice problems", "duration": "45 min", "completed": False},
                {"task": "Debug and refactor code", "duration": "30 min", "completed": False}
            ]
        elif day_type["type"] == "review":
            plan["tasks"] = [
                {"task": "Review notes from the week", "duration": "30 min", "completed": False},
                {"task": "Summarize key learnings", "duration": "30 min", "completed": False},
                {"task": "Identify knowledge gaps", "duration": "20 min", "completed": False}
            ]
        else:  # project
            plan["tasks"] = [
                {"task": "Work on module project", "duration": "90 min", "completed": False},
                {"task": "Document progress", "duration": "20 min", "completed": False},
                {"task": "Seek feedback", "duration": "15 min", "completed": False}
            ]
        
        # Add resources for the day
        if module.get("resources"):
            plan["resources_for_today"] = {
                "primary": module["resources"].get("primary", [])[:1] if day <= 2 else [],
                "practice": module["resources"].get("practice", []) if day_type["type"] == "practice" else []
            }
        
        daily_plans.append(plan)
    
    return daily_plans

@mcp.tool()
async def search_learning_resources(topic: str, num_results: int = 10) -> Dict[str, Any]:
    """
    Search for learning resources on a specific topic using DuckDuckGo
    
    Args:
        topic: The topic to search for learning resources
        num_results: Number of search results to retrieve (default: 10)
    
    Returns:
        Dictionary containing categorized learning resources
    """
    # Create targeted search queries
    queries = [
        f"{topic} tutorial beginner",
        f"{topic} documentation",
        f"{topic} online course",
        f"learn {topic} step by step"
    ]
    
    all_results = []
    for query in queries:
        results = await search_duckduckgo(query, num_results=num_results // len(queries))
        all_results.extend(results)
    
    # Analyze and categorize resources
    categorized_resources = analyze_learning_resources(all_results, topic)
    
    return {
        "topic": topic,
        "total_resources": len(all_results),
        "resources": categorized_resources,
        "search_queries_used": queries
    }

@mcp.tool()
async def generate_curriculum(
    user_id: str,
    topic: str,
    level: str = "beginner",
    duration_weeks: int = 4,
    focus_areas: Optional[List[str]] = None,
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    Generate a personalized curriculum based on topic and user preferences
    
    Args:
        user_id: Unique identifier for the user
        topic: The main topic to learn
        level: Skill level (beginner, intermediate, advanced)
        duration_weeks: Duration of the curriculum in weeks
        focus_areas: Optional specific areas to focus on
        use_llm: Whether to use LLM for intelligent generation (default: True)
    
    Returns:
        Complete curriculum with modules and resources
    """
    # Search for resources
    search_query = f"{topic} {' '.join(focus_areas) if focus_areas else ''}"
    search_results = await search_learning_resources(search_query, num_results=20)
    
    # Try LLM-based generation first if enabled
    if use_llm and llm_available:
        try:
            llm_curriculum = await generate_intelligent_curriculum_with_llm(
                topic=topic,
                level=level,
                duration_weeks=duration_weeks,
                focus_areas=focus_areas,
                user_context={
                    "user_id": user_id,
                    "resources_found": len(search_results.get("resources", {}))
                }
            )
            
            # Merge LLM curriculum with resource search results
            curriculum = {
                "title": f"{topic} Learning Path",
                "level": level,
                "duration_weeks": duration_weeks,
                "modules": llm_curriculum.get("modules", []),
                "overall_goal": llm_curriculum.get("overall_goal", f"Master {topic}"),
                "recommended_pace": llm_curriculum.get("recommended_pace", "Follow weekly schedule"),
                "resources": search_results["resources"],
                "generation_method": "llm_enhanced"
            }
            
            # Add resources to each module
            for module in curriculum["modules"]:
                module["resources"] = {
                    "primary": search_results["resources"].get("tutorials", [])[:2],
                    "supplementary": search_results["resources"].get("articles", [])[:2],
                    "practice": search_results["resources"].get("videos", [])[:1]
                }
                
        except Exception as e:
            print(f"LLM generation failed: {e}, falling back to rule-based")
            use_llm = False
    
    # Fallback to rule-based generation
    if not use_llm or not llm_available:
        curriculum = generate_curriculum_structure(
            topic=topic,
            level=level,
            duration_weeks=duration_weeks,
            resources=search_results["resources"]
        )
        curriculum["generation_method"] = "rule_based"
    
    # Add metadata
    curriculum["user_id"] = user_id
    curriculum["focus_areas"] = focus_areas or []
    curriculum["generated_at"] = datetime.now().isoformat()
    
    # Save to database
    curriculum_id = db.save_curriculum(user_id, curriculum)
    curriculum["curriculum_id"] = curriculum_id
    
    return curriculum

@mcp.tool()
async def create_daily_learning_plan(
    user_id: str,
    curriculum_id: int,
    week_number: int,
    days_per_week: int = 5
) -> Dict[str, Any]:
    """
    Create a daily learning plan for a specific week of the curriculum
    
    Args:
        user_id: User identifier
        curriculum_id: ID of the curriculum
        week_number: Week number to create plan for
        days_per_week: Number of study days per week (default: 5)
    
    Returns:
        Daily learning plan with tasks and resources
    """
    # Get curriculum
    curriculum = db.get_curriculum(user_id, curriculum_id)
    if not curriculum:
        return {"error": "Curriculum not found"}
    
    # Find the module for the specified week
    module = None
    for m in curriculum["modules"]:
        if m["week"] == week_number:
            module = m
            break
    
    if not module:
        return {"error": f"Week {week_number} not found in curriculum"}
    
    # Create daily plans
    daily_plans = create_daily_study_plan(module, days_per_week)
    
    # Save to database
    plan_data = {
        "week_number": week_number,
        "module_title": module["title"],
        "daily_plans": daily_plans,
        "created_at": datetime.now().isoformat()
    }
    db.save_daily_plan(user_id, curriculum_id, plan_data)
    
    return {
        "user_id": user_id,
        "curriculum_id": curriculum_id,
        "week_number": week_number,
        "module": module["title"],
        "daily_plans": daily_plans,
        "total_estimated_hours": module["estimated_hours"]
    }

@mcp.tool()
async def get_learning_plan(
    user_id: str,
    curriculum_id: int,
    week_number: Optional[int] = None
) -> Dict[str, Any]:
    """
    Retrieve learning plans for a user
    
    Args:
        user_id: User identifier
        curriculum_id: Curriculum ID
        week_number: Optional specific week number
    
    Returns:
        Learning plan(s) for the specified curriculum
    """
    curriculum = db.get_curriculum(user_id, curriculum_id)
    if not curriculum:
        return {"error": "Curriculum not found"}
    
    all_plans = db.get_daily_plans(user_id, curriculum_id)
    
    if week_number:
        # Filter for specific week
        week_plans = [p for p in all_plans if p.get("week_number") == week_number]
        if week_plans:
            return {
                "user_id": user_id,
                "curriculum_id": curriculum_id,
                "curriculum_title": curriculum["title"],
                "week_plan": week_plans[0]
            }
        else:
            return {"error": f"No plan found for week {week_number}"}
    
    return {
        "user_id": user_id,
        "curriculum_id": curriculum_id,
        "curriculum_title": curriculum["title"],
        "all_plans": all_plans,
        "total_weeks": curriculum["duration_weeks"]
    }

@mcp.tool()
async def update_learning_progress(
    user_id: str,
    curriculum_id: int,
    week_number: int,
    day_number: int,
    task_index: int,
    completed: bool = True
) -> Dict[str, Any]:
    """
    Update learning progress for a specific task
    
    Args:
        user_id: User identifier
        curriculum_id: Curriculum ID
        week_number: Week number
        day_number: Day number within the week
        task_index: Index of the task to update
        completed: Whether the task is completed
    
    Returns:
        Updated progress status
    """
    # Get the daily plans
    all_plans = db.get_daily_plans(user_id, curriculum_id)
    week_plan = None
    
    for plan in all_plans:
        if plan.get("week_number") == week_number:
            week_plan = plan
            break
    
    if not week_plan:
        return {"error": "Week plan not found"}
    
    # Update task completion
    if day_number <= len(week_plan["daily_plans"]):
        day_plan = week_plan["daily_plans"][day_number - 1]
        if task_index < len(day_plan["tasks"]):
            day_plan["tasks"][task_index]["completed"] = completed
            
            # Calculate progress
            total_tasks = sum(len(dp["tasks"]) for dp in week_plan["daily_plans"])
            completed_tasks = sum(
                sum(1 for task in dp["tasks"] if task.get("completed", False))
                for dp in week_plan["daily_plans"]
            )
            
            progress = {
                "week_number": week_number,
                "day_number": day_number,
                "task_completed": completed,
                "week_progress_percentage": round((completed_tasks / total_tasks) * 100, 2),
                "updated_at": datetime.now().isoformat()
            }
            
            db.update_progress(user_id, curriculum_id, day_number, progress)
            
            return {
                "user_id": user_id,
                "curriculum_id": curriculum_id,
                "progress": progress,
                "message": f"Task {'completed' if completed else 'marked incomplete'} successfully"
            }
    
    return {"error": "Invalid day or task index"}

@mcp.tool()
async def get_curriculum_summary(user_id: str) -> Dict[str, Any]:
    """
    Get summary of all curriculums for a user
    
    Args:
        user_id: User identifier
    
    Returns:
        Summary of all user's curriculums
    """
    if user_id not in db.curriculums:
        return {"user_id": user_id, "curriculums": [], "message": "No curriculums found"}
    
    summaries = []
    for curriculum in db.curriculums[user_id]:
        summary = {
            "curriculum_id": curriculum.get("id"),
            "title": curriculum.get("title"),
            "level": curriculum.get("level"),
            "duration_weeks": curriculum.get("duration_weeks"),
            "created_at": curriculum.get("created_at"),
            "modules_count": len(curriculum.get("modules", []))
        }
        summaries.append(summary)
    
    return {
        "user_id": user_id,
        "total_curriculums": len(summaries),
        "curriculums": summaries
    }

@mcp.tool()
async def analyze_learning_style(
    user_id: str,
    preferences: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze user's learning style and preferences using LLM
    
    Args:
        user_id: User identifier
        preferences: User's learning preferences (time availability, goals, experience)
    
    Returns:
        Personalized learning recommendations
    """
    if not llm_available:
        return {
            "error": "LLM not available",
            "fallback": "Using default learning style"
        }
    
    prompt = f"""Based on the following user preferences, provide personalized learning recommendations:
    
    Preferences:
    {json.dumps(preferences, indent=2)}
    
    Please analyze and provide:
    1. Recommended learning style (visual, auditory, kinesthetic, reading/writing)
    2. Optimal study schedule (time of day, duration, frequency)
    3. Suggested learning techniques
    4. Potential challenges and how to overcome them
    5. Motivation strategies
    
    Format as JSON with keys: learning_style, schedule, techniques, challenges, motivation
    """
    
    response = await analyze_with_llm(prompt, preferences)
    
    try:
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            return json.loads(json_match.group())
    except:
        pass
    
    return {
        "user_id": user_id,
        "analysis": response,
        "preferences": preferences
    }

@mcp.tool()
async def get_learning_advice(
    topic: str,
    current_level: str,
    target_level: str,
    timeframe: str
) -> Dict[str, Any]:
    """
    Get expert learning advice using LLM
    
    Args:
        topic: The subject to learn
        current_level: Current skill level
        target_level: Desired skill level
        timeframe: Available time to reach target
    
    Returns:
        Expert advice and recommendations
    """
    if not llm_available:
        return {
            "advice": f"Progress from {current_level} to {target_level} in {topic} through consistent practice.",
            "method": "rule_based"
        }
    
    prompt = f"""As an expert learning advisor, provide detailed advice for:
    
    Topic: {topic}
    Current Level: {current_level}
    Target Level: {target_level}
    Timeframe: {timeframe}
    
    Please provide:
    1. Feasibility assessment
    2. Key milestones to track progress
    3. Most efficient learning path
    4. Common pitfalls to avoid
    5. Success metrics
    6. Resource recommendations
    
    Be specific and actionable.
    """
    
    advice = await analyze_with_llm(prompt, {
        "topic": topic,
        "current": current_level,
        "target": target_level,
        "time": timeframe
    })
    
    return {
        "topic": topic,
        "advice": advice,
        "current_level": current_level,
        "target_level": target_level,
        "timeframe": timeframe,
        "method": "llm_generated"
    }

@mcp.tool()
async def generate_quiz(
    user_id: str,
    curriculum_id: int,
    week_number: int,
    num_questions: int = 5
) -> Dict[str, Any]:
    """
    Generate a quiz for a specific week using LLM
    
    Args:
        user_id: User identifier
        curriculum_id: Curriculum ID
        week_number: Week to generate quiz for
        num_questions: Number of questions (default: 5)
    
    Returns:
        Quiz with questions and answers
    """
    # Get curriculum and module
    curriculum = db.get_curriculum(user_id, curriculum_id)
    if not curriculum:
        return {"error": "Curriculum not found"}
    
    module = None
    for m in curriculum["modules"]:
        if m["week"] == week_number:
            module = m
            break
    
    if not module:
        return {"error": f"Week {week_number} not found"}
    
    if not llm_available:
        # Simple fallback quiz
        return {
            "quiz_id": f"{curriculum_id}_{week_number}",
            "module": module["title"],
            "questions": [
                {
                    "question": f"What is the main concept of {module['title']}?",
                    "type": "open_ended",
                    "hint": "Think about the key objectives"
                }
            ],
            "method": "rule_based"
        }
    
    prompt = f"""Create a quiz with {num_questions} questions for:
    
    Module: {module['title']}
    Week: {week_number}
    Level: {curriculum.get('level', 'beginner')}
    Objectives: {json.dumps(module.get('objectives', []))}
    Key Concepts: {json.dumps(module.get('key_concepts', []))}
    
    Generate diverse question types:
    - Multiple choice (provide 4 options with 1 correct answer)
    - True/False
    - Short answer
    - Code completion (if applicable)
    
    Format as JSON array with structure:
    {{
        "questions": [
            {{
                "id": 1,
                "question": "Question text",
                "type": "multiple_choice|true_false|short_answer|code",
                "options": ["A", "B", "C", "D"],  // for multiple choice
                "correct_answer": "answer",
                "explanation": "Why this is correct",
                "difficulty": "easy|medium|hard"
            }}
        ]
    }}
    """
    
    response = await analyze_with_llm(prompt, {"module": module})
    
    try:
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            quiz_data = json.loads(json_match.group())
            return {
                "quiz_id": f"{curriculum_id}_{week_number}",
                "user_id": user_id,
                "curriculum_id": curriculum_id,
                "week_number": week_number,
                "module": module["title"],
                "questions": quiz_data.get("questions", []),
                "created_at": datetime.now().isoformat(),
                "method": "llm_generated"
            }
    except Exception as e:
        print(f"Failed to parse quiz: {e}")
    
    return {
        "quiz_id": f"{curriculum_id}_{week_number}",
        "module": module["title"],
        "quiz_content": response,
        "method": "llm_raw"
    }

@mcp.tool()
async def provide_learning_feedback(
    user_id: str,
    curriculum_id: int,
    week_number: int,
    user_reflection: str
) -> Dict[str, Any]:
    """
    Provide personalized feedback on learning progress using LLM
    
    Args:
        user_id: User identifier
        curriculum_id: Curriculum ID
        week_number: Current week number
        user_reflection: User's self-reflection on their progress
    
    Returns:
        Personalized feedback and recommendations
    """
    # Get progress data
    curriculum = db.get_curriculum(user_id, curriculum_id)
    if not curriculum:
        return {"error": "Curriculum not found"}
    
    if not llm_available:
        return {
            "feedback": "Keep up the good work! Continue with your daily practice.",
            "method": "rule_based"
        }
    
    prompt = f"""As a supportive learning coach, provide feedback for:
    
    Course: {curriculum.get('title', 'Unknown')}
    Current Week: {week_number} of {curriculum.get('duration_weeks', 0)}
    Level: {curriculum.get('level', 'beginner')}
    
    Student's Reflection:
    {user_reflection}
    
    Please provide:
    1. Acknowledgment of their progress
    2. Constructive feedback on areas mentioned
    3. Specific suggestions for improvement
    4. Encouragement and motivation
    5. Next steps recommendation
    
    Be empathetic, specific, and actionable.
    """
    
    feedback = await analyze_with_llm(prompt, {
        "user_id": user_id,
        "week": week_number,
        "reflection": user_reflection
    })
    
    return {
        "user_id": user_id,
        "curriculum_id": curriculum_id,
        "week_number": week_number,
        "feedback": feedback,
        "timestamp": datetime.now().isoformat(),
        "method": "llm_generated"
    }

@mcp.tool()
async def export_user_data(user_id: str) -> Dict[str, Any]:
    """
    Export all data for a specific user
    
    Args:
        user_id: User identifier
    
    Returns:
        Complete user data export
    """
    export_data = {
        "user_id": user_id,
        "export_timestamp": datetime.now().isoformat(),
        "curriculums": db.curriculums.get(user_id, []),
        "daily_plans": {},
        "progress": {}
    }
    
    # Get all daily plans for this user
    for key, plans in db.daily_plans.items():
        if key.startswith(f"{user_id}_"):
            export_data["daily_plans"][key] = plans
    
    # Get all progress for this user
    for key, progress in db.learning_progress.items():
        if key.startswith(f"{user_id}_"):
            export_data["progress"][key] = progress
    
    return export_data

@mcp.tool()
async def get_database_stats() -> Dict[str, Any]:
    """
    Get database statistics
    
    Returns:
        Database usage statistics
    """
    total_curriculums = sum(len(curricula) for curricula in db.curriculums.values())
    
    return {
        "total_users": len(db.curriculums),
        "total_curriculums": total_curriculums,
        "total_daily_plans": len(db.daily_plans),
        "total_progress_records": len(db.learning_progress),
        "users": list(db.curriculums.keys()),
        "data_directory": db.data_dir,
        "timestamp": datetime.now().isoformat()
    }

@mcp.tool()
async def backup_database(backup_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a backup of the entire database
    
    Args:
        backup_name: Optional custom backup name
    
    Returns:
        Backup information
    """
    if not backup_name:
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    backup_dir = os.path.join(db.data_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    backup_file = os.path.join(backup_dir, f"{backup_name}.json")
    
    backup_data = {
        "backup_timestamp": datetime.now().isoformat(),
        "curriculums": db.curriculums,
        "daily_plans": db.daily_plans,
        "learning_progress": db.learning_progress
    }
    
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "backup_name": backup_name,
            "backup_file": backup_file,
            "timestamp": backup_data["backup_timestamp"],
            "total_size": os.path.getsize(backup_file)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "backup_name": backup_name
        }

if __name__ == "__main__":
    mcp.run(transport="stdio")