# 🎨 PDF Art Collection Extractor - Clean Version

## 🚀 **QUICK START**

```bash
# 1. Launch the professional validation interface
start_unified_validation.bat

# 2. Open your browser
http://localhost:5000

# 3. Extract artworks from PDF
python main.py
```

## 📁 **PROJECT STRUCTURE (CLEAN)**

### **🔧 CORE FILES**
- `main.py` - **Main entry point** for PDF extraction
- `unified_validation_server.py` - **Unified server** (Picasso + Dubuffet)
- `professional_validation_interface.html` - **Modern validation UI**
- `start_unified_validation.bat` - **Launch script**

### **📦 CORE MODULES**
```
├── core/
│   └── pdf_extractor.py          # Main extraction engine
├── detectors/
│   ├── ultra_detector.py         # Advanced image detection
│   ├── color_detector.py         # Color-based detection
│   └── template_detector.py      # Template matching
├── artwork_collections/
│   ├── picasso_collection.py     # Picasso-specific logic
│   └── dubuffet_collection.py    # Dubuffet-specific logic
├── config/
│   └── settings.py               # Configuration
└── utils/
    ├── logger.py                 # Logging system
    ├── image_utils.py            # Image processing
    └── file_utils.py             # File operations
```

### **🎨 SPECIALIZED TOOLS**
- `dubuffet_ocr_extractor.py` - **OCR for Dubuffet captions**
- `toc_planches.py` - **Table of contents extraction**

### **📊 DATA**
- `extractions_ultra/` - **Extraction results** (Picasso & Dubuffet)
- `requirements.txt` - **Python dependencies**

### **🗂️ ARCHIVED FILES**
- `_backup/` - **Old files safely archived**
  - `old_interfaces/` - Previous validation interfaces
  - `debug_scripts/` - Development/debug scripts  
  - `demos/` - Demo and test files

## 🎯 **FEATURES**

### **🎭 Picasso Collection**
- ✅ Classic artwork detection
- ✅ Table of contents parsing
- ✅ Professional validation interface

### **🎨 Dubuffet Collection**
- ✅ Advanced OCR caption extraction
- ✅ Individual artwork JSON generation
- ✅ Debug OCR images
- ✅ Automatic artwork numbering
- ✅ Page offset correction

### **🌟 Professional Interface**
- ✅ **Modern design** with Lucide icons
- ✅ **Responsive layout** (desktop + mobile)
- ✅ **Real-time validation** statistics
- ✅ **Session switching** (Picasso ↔ Dubuffet)
- ✅ **Page synchronization** (PDF ↔ Images)
- ✅ **Export & save** functionality

## 🔧 **TECHNICAL DETAILS**

### **Collections System**
The system automatically detects collection type:
- **Picasso**: `PICASSO` in session name
- **Dubuffet**: `DUBUFFET` in session name

### **Page Offset Correction**
Automatically handles page offset between PDF and extraction:
```python
# Example: Dubuffet extraction starts at PDF page 12
# Interface Page 1 → PDF Page 12 → Directory page_012/
```

### **OCR Integration (Dubuffet)**
- **Immediate OCR**: Captions extracted during image detection
- **Individual JSONs**: `oeuvre_XXX.json` per artwork
- **Debug images**: OCR region visualization
- **Fallback system**: Multiple OCR attempts with different settings

## 📋 **USAGE WORKFLOWS**

### **1. Extract Artworks**
```bash
python main.py
# → Select PDF
# → Choose collection (auto-detected)
# → Wait for extraction
```

### **2. Validate Results**
```bash
start_unified_validation.bat
# → Open http://localhost:5000
# → Select session
# → Validate images page by page
# → Export validated images
```

### **3. Access OCR Data (Dubuffet)**
- Individual JSONs in each `page_XXX/` folder
- Debug OCR images show extraction regions
- Professional interface displays OCR details

## 🚀 **PERFORMANCE**

- **Fast Mode**: Reduced processing for older hardware
- **Threading**: OCR operations with timeout protection
- **Memory Optimized**: Efficient image processing
- **Page-by-page**: Progressive results display

## 📝 **CHANGELOG**

### **v3.0 - Professional Clean Version**
- ✅ Unified professional interface
- ✅ Page offset correction
- ✅ Modern design with real icons
- ✅ Archived obsolete files
- ✅ Clean project structure
- ✅ Comprehensive documentation

---

**Ready to use! 🎉 Launch `start_unified_validation.bat` and enjoy the professional experience!**
