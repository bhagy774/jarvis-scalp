import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Import the module to be tested
import jarvis_rag_chat

def test_initialize_database_no_files_exits():
    """Test that initialize_database exits when no knowledge base files are found."""
    with patch('os.path.exists', return_value=False), \
         patch('sys.exit') as mock_exit, \
         patch('builtins.print'):

        try:
            jarvis_rag_chat.initialize_database()
        except BaseException as e:
            # sys.exit will actually raise SystemExit if not fully mocked to return normally,
            # or if the real sys.exit gets called. By mocking sys.exit, it shouldn't raise, but let's be safe.
            pass

        # Verify sys.exit(1) was called
        # We use assert_called_with to just check it was called with 1 at least once since the loop might call other exits if not handled well
        # but in this case it should just exit early. If it's called multiple times, we might need to check the call list.
        mock_exit.assert_called_with(1)

def test_initialize_database_success():
    """Test that initialize_database successfully creates and returns a vectorstore."""
    mock_document = MagicMock()
    mock_document.page_content = "test content"

    mock_loader_instance = MagicMock()
    mock_loader_instance.load.return_value = [mock_document]

    with patch('os.path.exists', return_value=True), \
         patch('jarvis_rag_chat.TextLoader', return_value=mock_loader_instance), \
         patch('jarvis_rag_chat.RecursiveCharacterTextSplitter') as MockSplitter, \
         patch('jarvis_rag_chat.OllamaEmbeddings') as MockEmbeddings, \
         patch('jarvis_rag_chat.Chroma.from_documents') as mock_from_documents, \
         patch('builtins.print'):

        # Setup mock behavior
        mock_splitter_instance = MagicMock()
        mock_splitter_instance.split_documents.return_value = [mock_document]
        MockSplitter.return_value = mock_splitter_instance

        mock_vectorstore = MagicMock()
        mock_from_documents.return_value = mock_vectorstore

        # Run function
        result = jarvis_rag_chat.initialize_database()

        # Verify result is the mock vectorstore
        assert result == mock_vectorstore

        # Verify from_documents was called with correct parameters
        mock_from_documents.assert_called_once()
        kwargs = mock_from_documents.call_args[1]
        assert kwargs['documents'] == [mock_document]
        assert 'embedding' in kwargs
        assert kwargs['persist_directory'] == jarvis_rag_chat.DB_DIR

def test_initialize_database_chroma_error():
    """Test that initialize_database handles ChromaDB creation errors and exits."""
    mock_document = MagicMock()
    mock_loader_instance = MagicMock()
    mock_loader_instance.load.return_value = [mock_document]

    with patch('os.path.exists', return_value=True), \
         patch('jarvis_rag_chat.TextLoader', return_value=mock_loader_instance), \
         patch('jarvis_rag_chat.RecursiveCharacterTextSplitter'), \
         patch('jarvis_rag_chat.OllamaEmbeddings'), \
         patch('jarvis_rag_chat.Chroma.from_documents', side_effect=Exception("Chroma error")), \
         patch('sys.exit') as mock_exit, \
         patch('builtins.print'):

        jarvis_rag_chat.initialize_database()

        # Verify sys.exit(1) was called due to the exception
        mock_exit.assert_called_once_with(1)

def test_main_new_db():
    """Test main loop behavior when a new DB needs to be created."""
    mock_vectorstore = MagicMock()
    mock_retriever = MagicMock()
    mock_vectorstore.as_retriever.return_value = mock_retriever

    mock_qa_chain = MagicMock()

    with patch('os.path.exists', return_value=False), \
         patch('jarvis_rag_chat.initialize_database', return_value=mock_vectorstore) as mock_init_db, \
         patch('jarvis_rag_chat.Ollama'), \
         patch('jarvis_rag_chat.RetrievalQA.from_chain_type', return_value=mock_qa_chain), \
         patch('builtins.input', side_effect=['quit']), \
         patch('builtins.print'):

        jarvis_rag_chat.main()

        # Verify initialize_database was called since db didn't exist
        mock_init_db.assert_called_once()

        # The test passing means the side_effect sequence was consumed or hit StopIteration if more inputs were requested. But here we expect it to break the loop on 'quit'

def test_main_existing_db():
    """Test main loop behavior when a DB already exists."""
    mock_qa_chain = MagicMock()
    mock_qa_chain.invoke.return_value = {'result': 'Mocked response'}

    # We need os.path.exists to return True for the DB_DIR but we also need os.listdir to return something
    def mock_exists(path):
        return True

    def mock_listdir(path):
        return ['some_file.db']

    with patch('os.path.exists', side_effect=mock_exists), \
         patch('os.listdir', side_effect=mock_listdir), \
         patch('jarvis_rag_chat.initialize_database') as mock_init_db, \
         patch('jarvis_rag_chat.OllamaEmbeddings'), \
         patch('jarvis_rag_chat.Chroma'), \
         patch('jarvis_rag_chat.Ollama'), \
         patch('jarvis_rag_chat.RetrievalQA.from_chain_type', return_value=mock_qa_chain), \
         patch('builtins.input', side_effect=['What is SMC?', 'exit']), \
         patch('builtins.print'):

        jarvis_rag_chat.main()

        # Verify initialize_database was NOT called
        mock_init_db.assert_not_called()

        # Verify qa_chain.invoke was called for the first input
        mock_qa_chain.invoke.assert_called_once_with({"query": "What is SMC?"})
