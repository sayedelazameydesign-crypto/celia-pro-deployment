# How We Built Semantic Memory for Celia.pro

*A deep dive into building an AI assistant that understands meaning, not just keywords*

---

## The Problem: Why Most AI Assistants Fail at Memory

If you've ever used ChatGPT, Claude, or any AI assistant, you've experienced this:

```
You: "I prefer vegetarian restaurants"
AI: "Got it! I'll remember that."

[Next day]

You: "Find me good restaurants in Cairo"
AI: "Here are some great steak houses..."
You: "But I said I prefer vegetarian!"
AI: "I apologize for the confusion..."
```

Sound familiar? The AI "forgot" your preference. Not because it's stupid, but because most AI systems use **keyword matching** or **simple vector storage** without understanding **semantic relationships**.

At Celia.pro, we decided to fix this. Here's how.

---

## What is Semantic Memory?

Semantic memory is the ability to understand **meaning** and **relationships** between concepts, not just store words.

Example:
- "The weather is hot" 
- "It's really warm today"
- "Temperature is high"

These three sentences mean the **same thing**, but use different words. A keyword-based system would treat them as different. A semantic system understands they're related.

---

## Our Architecture

### 1. Vector Embeddings: Converting Text to Numbers

The first step is converting text into **vector embeddings** - numerical representations that capture semantic meaning.

We use **sentence-transformers** with the `all-MiniLM-L6-v2` model:

```python
from core.embeddings import EmbeddingProvider

provider = EmbeddingProvider(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# Generate 384-dimensional vector
vector = provider.embed("The weather is hot")
# Output: [0.123, -0.456, 0.789, ...] (384 dimensions)
```

**Why this model?**
- **Fast**: ~10ms per text
- **Lightweight**: ~90MB model size
- **Multilingual**: Supports Arabic + English
- **Accurate**: Good balance of speed vs accuracy

### 2. Storage: PostgreSQL + JSON for Vectors

We initially considered specialized vector databases like Pinecone or Weaviate, but decided to stick with **PostgreSQL** for simplicity:

```python
# database/models.py
class MemoryItem(Base):
    __tablename__ = "memory_items"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    key = Column(String(255), index=True)
    value = Column(JSON)              # The actual memory content
    memory_metadata = Column(JSON)    # Tags, category, importance
    vector_256 = Column(JSON)         # 384-dimensional embedding
    state = Column(JSON)              # Access count, last used
    expires_at = Column(DateTime)     # TTL support
    created_at = Column(DateTime)
```

**Why JSON for vectors?**
- No need for additional database extensions
- Works with any PostgreSQL setup
- Easy to migrate later to pgvector if needed
- Good enough for our scale (< 1M memories)

### 3. Semantic Search: Cosine Similarity

When retrieving memories, we use **cosine similarity** to find semantically similar vectors:

```python
# database/repositories.py
async def search_by_vector(
    self, 
    user_id: str, 
    query_vector: List[float], 
    limit: int = 5
) -> List[MemoryItem]:
    # Get all memories for user
    memories = await self.get_user_memories(user_id)
    
    # Calculate cosine similarity
    similarities = []
    for memory in memories:
        if memory.vector_256:
            similarity = cosine_similarity(
                query_vector, 
                memory.vector_256
            )
            similarities.append((similarity, memory))
    
    # Sort by similarity and return top results
    similarities.sort(key=lambda x: x[0], reverse=True)
    return [mem for _, mem in similarities[:limit]]
```

**Cosine similarity formula:**
```
similarity = (A · B) / (||A|| × ||B||)
```

Where:
- `A · B` = dot product of vectors
- `||A||` = magnitude of vector A
- Result ranges from -1 (opposite) to 1 (identical)

---

## The Secret Sauce: Combining Everything

Here's how it all works together:

### Step 1: Store Memory
```python
# User says: "I prefer vegetarian restaurants"
await reflection_layer.store_lesson(
    situation="User expressing food preferences",
    action="Store preference",
    outcome="success",
    lesson="User prefers vegetarian restaurants",
    tags=["food", "preference", "vegetarian"]
)

# Behind the scenes:
# 1. Generate embedding: [0.234, -0.567, 0.891, ...]
# 2. Store in database with vector
# 3. Add metadata tags
```

### Step 2: Retrieve Relevant Memories
```python
# User asks: "Find restaurants in Cairo"
query_vector = provider.embed("Find restaurants in Cairo")
# Vector: [0.198, -0.445, 0.712, ...]

# Search for similar memories
memories = await memory_repo.search_by_vector(
    user_id=user_id,
    query_vector=query_vector,
    limit=5
)

# Result: Finds "User prefers vegetarian restaurants"
# because vectors are semantically similar!
```

### Step 3: Enhance Prompt
```python
# Add retrieved memories to the prompt
enhanced_prompt = base_prompt + """

## Relevant Memories:
1. User prefers vegetarian restaurants (similarity: 0.87)
2. User lives in Cairo (similarity: 0.72)
"""

# Send to LLM with enhanced context
response = await llm.chat(enhanced_prompt)
# Result: "Here are great vegetarian restaurants in Cairo..."
```

---

## Performance Optimization

### Challenge: Speed

Calculating cosine similarity for thousands of memories can be slow.

### Solution: Two-Tier Search

```python
async def search_by_vector(self, user_id, query_vector, limit=5):
    # Tier 1: Quick filter by metadata (tags, category)
    candidate_memories = await self.filter_by_metadata(
        user_id=user_id,
        tags=["food", "restaurant"]  # Quick filter
    )
    
    # Tier 2: Precise semantic search on candidates only
    similarities = []
    for memory in candidate_memories:
        similarity = cosine_similarity(query_vector, memory.vector_256)
        similarities.append((similarity, memory))
    
    similarities.sort(key=lambda x: x[0], reverse=True)
    return [mem for _, mem in similarities[:limit]]
```

**Result**: 10x faster than searching all memories

---

## Handling Multilingual Content

### Challenge: Arabic + English

Arabic and English have different character sets, making direct vector comparison difficult.

### Solution: Language-Agnostic Embeddings

The `all-MiniLM-L6-v2` model is trained on **multilingual data**, so it creates similar vectors for semantically similar sentences across languages:

```python
# English
vector_en = provider.embed("I like vegetarian food")
# [0.234, -0.567, 0.891, ...]

# Arabic
vector_ar = provider.embed("أحب الطعام النباتي")
# [0.231, -0.562, 0.887, ...]  # Very similar!

# Similarity: 0.95 (very high!)
```

---

## Lessons Learned

### 1. Start Simple, Optimize Later

We started with simple JSON storage for vectors. Only optimized when we hit performance issues.

**Don't over-engineer from day one.**

### 2. Metadata Matters

Vectors alone aren't enough. Tags and categories help with quick filtering:

```python
memory_metadata = {
    "category": "preference",
    "tags": ["food", "vegetarian"],
    "importance": 0.9
}
```

### 3. TTL is Important

Not all memories should last forever. We added `expires_at` for temporary memories:

```python
# Store temporary memory (expires in 24 hours)
await memory_repo.store(
    key="temporary_context",
    value="User is planning a trip",
    ttl_seconds=86400  # 24 hours
)
```

### 4. Test with Real Data

Unit tests are great, but nothing beats testing with real user data. We found edge cases we never imagined:
- Mixed Arabic/English sentences
- Slang and dialects
- Very long conversations

---

## What's Next?

### 1. Migration to pgvector

For better performance at scale, we're planning to migrate to PostgreSQL's native vector extension:

```sql
-- Future: pgvector extension
ALTER TABLE memory_items 
ADD COLUMN vector vector(384);

CREATE INDEX idx_vector ON memory_items 
USING ivfflat (vector vector_cosine_ops);
```

### 2. Hierarchical Memory

Currently, all memories are flat. We're exploring hierarchical memory structures:
- Short-term memory (current conversation)
- Medium-term memory (recent days)
- Long-term memory (permanent knowledge)

### 3. Memory Consolidation

Like human sleep, we want to implement "memory consolidation" - merging similar memories and strengthening important ones.

---

## Try It Yourself

Want to see semantic memory in action?

**[Try Celia.pro for free](https://celia.pro)** - No credit card required.

Or check out our **[GitHub repository](https://github.com/celia-pro/celia)** to see the code.

---

## Conclusion

Building semantic memory wasn't easy, but it was worth it. The result? An AI assistant that actually **understands** you, not just stores your words.

The key takeaways:
1. **Vector embeddings** capture semantic meaning
2. **Cosine similarity** finds related concepts
3. **Metadata** helps with quick filtering
4. **Start simple**, optimize later
5. **Test with real data**

We're just getting started. Follow us for more technical deep dives!

---

*Written by the Celia.pro team. We're building the future of AI assistants, one blog post at a time.*

**[Subscribe to our newsletter](https://celia.pro/newsletter)** for more technical articles.

---

## Resources

- [Sentence Transformers Documentation](https://www.sbert.net/)
- [PostgreSQL JSON Documentation](https://www.postgresql.org/docs/current/datatype-json.html)
- [Cosine Similarity Explained](https://en.wikipedia.org/wiki/Cosine_similarity)
- [Celia.pro GitHub](https://github.com/celia-pro/celia)

---

*Tags: #AI #MachineLearning #NaturalLanguageProcessing #SemanticMemory #VectorEmbeddings #PostgreSQL #Python*
