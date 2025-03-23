import os
import time
import tempfile
from flask import Flask, request, render_template, flash
from werkzeug.utils import secure_filename
from langchain_community.document_loaders import CSVLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_together import Together
from langchain_core.documents import Document
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Debug: Print all environment variables to confirm loading
print("Environment variables loaded:")
for key, value in os.environ.items():
    if key == "TOGETHER_API_KEY":
        print(f"{key}: {value}")
    else:
        print(f"{key}: [hidden]")

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = "supersecretkey"

# Use an absolute path for the uploads directory
UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"csv", "pdf"}

# Path to store FAISS index
FAISS_INDEX_PATH = os.path.join(tempfile.gettempdir(), "faiss_index")

# Debug: Print resolved paths
print(f"Resolved UPLOAD_FOLDER path: {UPLOAD_FOLDER}")
print(f"Resolved FAISS_INDEX_PATH: {FAISS_INDEX_PATH}")

# Ensure the uploads directory exists and has proper permissions
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    print(f"Created/Verified uploads directory: {UPLOAD_FOLDER}")
    test_file = os.path.join(UPLOAD_FOLDER, "test.txt")
    with open(test_file, "w") as f:
        f.write("test")
    os.remove(test_file)
    print(f"Successfully tested write permissions for: {UPLOAD_FOLDER}")
except Exception as e:
    print(f"Error with uploads directory: {str(e)}")
    UPLOAD_FOLDER = tempfile.gettempdir()
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    print(f"Falling back to temporary directory: {UPLOAD_FOLDER}")

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def load_documents(csv_path, pdf_path):
    print(f"Loading CSV: {csv_path}")
    csv_loader = CSVLoader(file_path=csv_path)
    csv_docs = csv_loader.load()
    print(f"Loading PDF: {pdf_path}")
    pdf_loader = PyPDFLoader(pdf_path)
    pdf_docs = pdf_loader.load()
    return csv_docs + pdf_docs

def split_documents(docs):
    print("Splitting documents...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    return text_splitter.split_documents(docs)

def setup_vector_store(docs):
    print("Setting up vector store...")
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_store = FAISS.from_documents(docs, embeddings)
    vector_store.save_local(FAISS_INDEX_PATH)
    print(f"Saved FAISS index to: {FAISS_INDEX_PATH}")
    return vector_store

def load_vector_store():
    print("Loading vector store from disk...")
    if not os.path.exists(FAISS_INDEX_PATH):
        raise FileNotFoundError(f"FAISS index not found at {FAISS_INDEX_PATH}. Please upload files first.")
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    print(f"Attempting to load FAISS index from: {FAISS_INDEX_PATH}")
    # Enable deserialization (safe since we created the file)
    vector_store = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    print("Successfully loaded FAISS index.")
    return vector_store

def setup_rag_chain(vector_store):
    print("Setting up RAG chain...")
    api_key = os.environ.get("TOGETHER_API_KEY")
    print(f"Raw TOGETHER_API_KEY from os.environ: {api_key}")
    if not api_key:
        print("Environment variables available:", list(os.environ.keys()))
        raise ValueError("TOGETHER_API_KEY environment variable is not set. Please set it before running the application.")
    if not isinstance(api_key, str) or api_key.strip() == "":
        raise ValueError(f"TOGETHER_API_KEY must be a non-empty string. Current value: {api_key}")
    print("TOGETHER_API_KEY:", api_key)
    llm = Together(
        model="meta-llama/Llama-3-70b-chat-hf",
        together_api_key=api_key,
        temperature=0.7
    )
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vector_store.as_retriever(search_kwargs={"k": 2})
    )

@app.route("/", methods=["GET", "POST"])
def index():
    response = None
    
    # Handle file upload
    if request.method == "POST" and "csv_file" in request.files:
        csv_file = request.files["csv_file"]
        pdf_file = request.files["pdf_file"]
        
        if not csv_file or not pdf_file:
            flash("Please upload both CSV and PDF files.")
        elif csv_file.filename == "" or pdf_file.filename == "":
            flash("No selected file.")
        elif csv_file and allowed_file(csv_file.filename) and pdf_file and allowed_file(pdf_file.filename):
            timestamp = str(int(time.time()))
            csv_filename = secure_filename(csv_file.filename).replace(".csv", f"_{timestamp}.csv")
            pdf_filename = secure_filename(pdf_file.filename).replace(".pdf", f"_{timestamp}.pdf")
            csv_path = os.path.join(app.config["UPLOAD_FOLDER"], csv_filename)
            pdf_path = os.path.join(app.config["UPLOAD_FOLDER"], pdf_filename)
            
            try:
                print(f"Attempting to save CSV to: {csv_path}")
                print(f"Attempting to save PDF to: {pdf_path}")
                print(f"Checking if CSV path is writable: {os.access(os.path.dirname(csv_path), os.W_OK)}")
                print(f"Checking if PDF path is writable: {os.access(os.path.dirname(pdf_path), os.W_OK)}")
                
                for path in [csv_path, pdf_path]:
                    if os.path.exists(path):
                        print(f"Deleting existing file: {path}")
                        for attempt in range(3):
                            try:
                                os.remove(path)
                                print(f"Successfully deleted: {path}")
                                break
                            except PermissionError as e:
                                if attempt < 2:
                                    print(f"File {path} is locked, retrying in 1 second... (Attempt {attempt + 1}/3)")
                                    time.sleep(1)
                                else:
                                    raise Exception(f"Cannot delete {path}: {str(e)}. The file might be open in another program (e.g., Excel). Please close it and try again.")
                
                csv_file.save(csv_path)
                pdf_file.save(pdf_path)
                print(f"Saved CSV to: {csv_path}")
                print(f"Saved PDF to: {pdf_path}")
                if not os.path.exists(csv_path) or not os.path.exists(pdf_path):
                    raise FileNotFoundError("Files failed to save.")
                
                docs = load_documents(csv_path, pdf_path)
                split_docs = split_documents(docs)
                vector_store = setup_vector_store(split_docs)
                rag_chain = setup_rag_chain(vector_store)
                flash("Files uploaded and processed successfully!")
            except Exception as e:
                flash(f"Error processing files: {str(e)}")
    
    # Handle query submission
    if request.method == "POST" and "query" in request.form:
        query = request.form.get("query").strip()
        if not query:
            flash("Please enter a query.")
        else:
            try:
                # Check if FAISS index exists before loading
                if not os.path.exists(FAISS_INDEX_PATH):
                    flash("Please upload files first before querying.")
                else:
                    vector_store = load_vector_store()
                    rag_chain = setup_rag_chain(vector_store)
                    print(f"Processing query: {query}")
                    result_dict = rag_chain.invoke(query)
                    response = result_dict.get('result', "No result found.").strip()
            except Exception as e:
                flash(f"Error querying: {str(e)}")
    
    return render_template("index.html", response=response)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))