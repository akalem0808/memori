# Add these methods to memory_utils.py MemoryProcessor class

    def get_whisper_model(self):
        """Get or initialize the Whisper model"""
        if not hasattr(self, '_whisper_model'):
            import whisper
            self._whisper_model = whisper.load_model("base")
        return self._whisper_model
    
    def get_emotion_analyzer(self):
        """Get the emotion analyzer model"""
        return self.emotion_analyzer
    
    def process_memory(self, memory_data: Dict) -> str:
        """Process memory data and store it"""
        # Convert dict to Memory object if needed
        if not isinstance(memory_data, Memory):
            try:
                memory = Memory(**memory_data)
            except Exception as e:
                raise ValueError(f"Invalid memory data: {e}")
        else:
            memory = memory_data
            
        # Store memory
        return self.store_memory(memory)
