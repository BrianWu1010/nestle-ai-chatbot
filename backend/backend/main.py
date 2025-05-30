import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from neo4j import GraphDatabase
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Neo4j driver
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# FastAPI app
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

class SearchQuery(BaseModel):
    query: str

@app.get("/")
async def root():
    return {"message": "Backend is running"}

@app.get("/greet")
async def greet():
    return {
        "results": [{
            "content": "Hey! I'm Smartie, your personal MadeWithNestlé assistant. Ask me anything, and I'll quickly search the entire site to find the answers you need!"
        }]
    }

@app.post("/search")
async def search(query: SearchQuery):
    try:
        user_input = query.query.lower()

        # Step 1: Detect if it's general conversation
        is_general = any(word in user_input for word in ["hello", "hi", "how are you", "what's up", "who are you", "tell me a joke"])

        if is_general:
            # Just let ChatGPT handle it with no context
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You're Smartie, an enthusiastic and helpful assistant who answers product and site-related questions for MadeWithNestlé. When possible, suggest relevant Nestlé products and include their links if available."},
                    {"role": "user", "content": query.query}
                ]
            )
            answer = completion.choices[0].message.content
            return {"results": [{"content": answer}]}

        # Step 2: Try Neo4j search
        slices = search_slices(query.query)

        # Fallback if no good context
        if not slices:
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You're Smartie, an enthusiastic and helpful assistant who answers product and site-related questions for MadeWithNestlé. When possible, suggest relevant Nestlé products and include their links if available."},
                    {"role": "user", "content": query.query}
                ]
            )
            answer = completion.choices[0].message.content
            return {"results": [{"content": answer}]}

        # Step 3: Use retrieved context with GPT
        prompt = "\n\n".join([s["content"] for s in slices[:3]])
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You're Smartie, an enthusiastic and helpful assistant who answers product and site-related questions for MadeWithNestlé. When possible, suggest relevant Nestlé products and include their links if available."},
                {"role": "user", "content": f"Context:\n{prompt}\n\nQuery: {query.query}"}
            ]
        )
        answer = completion.choices[0].message.content
        return {"results": [{"content": answer}]}

    except Exception as e:
        print("ERROR in /search:", e)
        return {"error": str(e)}

def search_slices(user_query: str):
    cypher = """
    CALL db.index.fulltext.queryNodes("sliceFulltext", $query) YIELD node, score
    RETURN node.content AS content, score
    LIMIT 5
    """
    with driver.session() as session:
        result = session.run(cypher, parameters={"query": user_query})
        return [{"content": record["content"], "score": record["score"]} for record in result]