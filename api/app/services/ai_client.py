async def ask_question(
    self,
    question: str,
    user_id: str,
    language: str = "auto",
    use_v2: bool = True  # НОВЫЙ параметр
) -> Optional[Dict]:
    """Ask AI system a question"""
    
    # Выбор endpoint
    endpoint = "/api/ask/v2" if use_v2 else "/api/ask"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                json={
                    "question": question,
                    "user_id": user_id,
                    "language": language
                }
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.error(f"Failed to ask question: {resp.status}")
                    return None
    except Exception as e:
        logger.error(f"Error asking question: {e}")
        return None