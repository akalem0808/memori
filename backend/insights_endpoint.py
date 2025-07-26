# Add this endpoint to memory_api.py

from memory_insights import InsightEngine

# Initialize the insight engine
insight_engine = InsightEngine()

@app.get("/insights", dependencies=[Depends(READ_PERMISSION)])
async def get_memory_insights():
    """Get insights based on user's memories"""
    try:
        # Get all memories
        memories = memory_processor.get_memories()
        
        # Generate insights
        insights = insight_engine.generate_insights(memories)
        
        return {
            "insights": insights,
            "count": len(insights),
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate insights"
        )
