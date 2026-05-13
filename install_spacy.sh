#!/bin/bash
# Install spaCy with Polish language model for NER-based sensitive data detection

echo "🚀 Installing spaCy for AI Agent Demo..."

# Install spaCy
pip install spacy>=3.7.0

# Download English language model (primary)
echo "📦 Downloading English language model..."
python -m spacy download en_core_web_sm

# Optional: Download medium model for better accuracy
echo "📦 Downloading enhanced English model..."
python -m spacy download en_core_web_md

echo "✅ spaCy installation complete!"
echo ""
echo "🔍 Available models:"
python -m spacy info

echo ""
echo "🧪 Testing NER detector..."
python -c "
try:
    from ai_agent_demo.core.ner_detector import SpacyNERDetector
    detector = SpacyNERDetector()
    print('✅ NER detector initialized successfully')
    print(f'📊 Model info: {detector.get_model_info()}')
except Exception as e:
    print(f'❌ Error: {e}')
"