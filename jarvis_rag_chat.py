import os
import sys

# Try to import necessary libraries, provide helpful error if missing
try:
    from langchain_community.document_loaders import TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.embeddings import OllamaEmbeddings
    from langchain_community.vectorstores import Chroma
    from langchain_community.llms import Ollama
    from langchain_classic.chains import RetrievalQA
    from langchain_core.prompts import PromptTemplate
except ImportError as e:
    print(f"Error: Missing libraries. {e}")
    print("Please run this command first:")
    print("pip install langchain langchain-community chromadb sentence-transformers")
    sys.exit(1)

# Configuration
BASE_DIR = r"c:\jarvis"
DB_DIR = os.path.join(BASE_DIR, "chroma_db")
LLM_MODEL = "llama3.2"
EMBEDDING_MODEL = "nomic-embed-text"

# System Prompt
PROMPT_TEMPLATE = """
You are Jarvis, a highly advanced institutional trading AI assistant. 
You are an expert in Smart Money Concepts (SMC), Order Flow, Options Greeks, and Algorithmic Trading.
Use the following pieces of context from your knowledge base to answer the user's question.
If you don't know the answer based on the context, use your vast general trading knowledge, but prioritize the context rules.
Always answer in a professional, concise, and institutional tone. You can reply in English, but if the user asks in Gujarati or Hindi, you should reply accordingly if possible.

Context:
{context}

User Question: {question}

Jarvis Answer:"""

def initialize_database():
    print("Loading Knowledge Base files...")
    
    # Target our specific files
    files_to_load = [
        "Jarvis_Master_Logic.md",
        "Knowledge_SMC_ICT.md",
        "Knowledge_OrderFlow_Volume.md",
        "Knowledge_Options_Greeks.md",
        "Knowledge_Microstructure.md"
    ]
    
    documents = []
    for filename in files_to_load:
        filepath = os.path.join(BASE_DIR, filename)
        if os.path.exists(filepath):
            loader = TextLoader(filepath, encoding='utf-8')
            documents.extend(loader.load())
            print(f"Loaded: {filename}")
        else:
            print(f"Warning: {filename} not found.")

    if not documents:
        print("No knowledge files found! Exiting.")
        sys.exit(1)

    print("Chunking documents...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_documents(documents)
    
    print(f"Created {len(chunks)} chunks. Generating embeddings and saving to ChromaDB...")
    print(f"Make sure Ollama is running and you have pulled '{EMBEDDING_MODEL}'!")
    
    try:
        # Initialize Ollama Embeddings
        embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
        
        # Create ChromaDB
        vectorstore = Chroma.from_documents(
            documents=chunks, 
            embedding=embeddings,
            persist_directory=DB_DIR
        )
        print(f"Database successfully saved at {DB_DIR}!")
        return vectorstore
    except Exception as e:
        print(f"\n[Error building database]: {e}")
        print("Did you start Ollama and run 'ollama pull nomic-embed-text'?")
        sys.exit(1)

def main():
    print("==================================================")
    print("      JARVIS INSTITUTIONAL RAG AI ASSISTANT       ")
    print("==================================================")
    
    # Check if DB exists, if not, create it
    if not os.path.exists(DB_DIR) or not os.listdir(DB_DIR):
        print("First time setup: Building vector database...")
        vectorstore = initialize_database()
    else:
        print("Connecting to existing ChromaDB...")
        try:
            embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
            vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
        except Exception as e:
            print(f"Failed to connect to database: {e}")
            sys.exit(1)
    
    # Setup the LLM
    print(f"Loading {LLM_MODEL}...")
    try:
        llm = Ollama(model=LLM_MODEL, temperature=0.1)
    except Exception as e:
        print(f"Failed to load LLM: {e}")
        print("Is Ollama running? Did you run 'ollama pull llama3.2'?")
        sys.exit(1)
    
    # Create Prompt Template
    PROMPT = PromptTemplate(
        template=PROMPT_TEMPLATE, input_variables=["context", "question"]
    )
    
    # Setup QA Chain
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(search_kwargs={"k": 4}),
        chain_type_kwargs={"prompt": PROMPT}
    )
    
    print("\n✅ Jarvis RAG Assistant is ONLINE!")
    print("Type 'exit' or 'quit' to stop.")
    print("--------------------------------------------------")
    
    while True:
        query = input("\n[You]: ")
        if query.lower() in ['exit', 'quit']:
            print("Shutting down Jarvis Assistant...")
            break
            
        if not query.strip():
            continue
            
        print("[Jarvis Thinking...]")
        try:
            response = qa_chain.invoke({"query": query})
            print(f"\n[Jarvis]: {response['result']}")
        except Exception as e:
            print(f"\n[Error]: {e}")
            print("Make sure Ollama is running in the background.")

if __name__ == "__main__":
    main()
