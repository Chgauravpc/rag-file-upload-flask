// Drag and Drop Functionality for CSV
const csvDropArea = document.getElementById('csv-drop-area');
const csvInput = document.getElementById('csv_file');

csvDropArea.addEventListener('click', () => csvInput.click());

csvDropArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    csvDropArea.classList.add('drag-over');
});

csvDropArea.addEventListener('dragleave', () => {
    csvDropArea.classList.remove('drag-over');
});

csvDropArea.addEventListener('drop', (e) => {
    e.preventDefault();
    csvDropArea.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length > 0 && files[0].name.endsWith('.csv')) {
        csvInput.files = files;
        csvDropArea.querySelector('p').textContent = `Selected: ${files[0].name}`;
    } else {
        alert('Please drop a valid CSV file.');
    }
});

csvInput.addEventListener('change', () => {
    if (csvInput.files.length > 0) {
        csvDropArea.querySelector('p').textContent = `Selected: ${csvInput.files[0].name}`;
    }
});

// Drag and Drop Functionality for PDF
const pdfDropArea = document.getElementById('pdf-drop-area');
const pdfInput = document.getElementById('pdf_file');

pdfDropArea.addEventListener('click', () => pdfInput.click());

pdfDropArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    pdfDropArea.classList.add('drag-over');
});

pdfDropArea.addEventListener('dragleave', () => {
    pdfDropArea.classList.remove('drag-over');
});

pdfDropArea.addEventListener('drop', (e) => {
    e.preventDefault();
    pdfDropArea.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length > 0 && files[0].name.endsWith('.pdf')) {
        pdfInput.files = files;
        pdfDropArea.querySelector('p').textContent = `Selected: ${files[0].name}`;
    } else {
        alert('Please drop a valid PDF file.');
    }
});

pdfInput.addEventListener('change', () => {
    if (pdfInput.files.length > 0) {
        pdfDropArea.querySelector('p').textContent = `Selected: ${pdfInput.files[0].name}`;
    }
});