import streamlit as st
import pymongo
from pymongo import MongoClient
import cloudinary
from cloudinary import CloudinaryImage
import cloudinary.uploader
import cloudinary.api
import os

# -----------------------------------------------------------------------------
# 1. SETUP / CONFIGURATION DICTIONARY
# -----------------------------------------------------------------------------
# 💡 Best Practice: Populate these variables directly, or map them to your system env variables.
CONFIG = {
    "MONGO_URI": os.environ.get("MONGO_URI", "mongodb://localhost:27017/"),
    "DB_NAME": os.environ.get("DB_NAME", "image_gallery"),
    "COLLECTION_NAME": os.environ.get("COLLECTION_NAME", "metadata"),
    
    "CLOUDINARY_CLOUD_NAME": os.environ.get("CLOUDINARY_CLOUD_NAME", "your_cloud_name"),
    "CLOUDINARY_API_KEY": os.environ.get("CLOUDINARY_API_KEY", "your_api_key"),
    "CLOUDINARY_API_SECRET": os.environ.get("CLOUDINARY_API_SECRET", "your_api_secret"),
}

# Streamlit secrets override fallback (if deployed on Streamlit Cloud)
if "MONGO_URI" in st.secrets:
    CONFIG.update(st.secrets)

# -----------------------------------------------------------------------------
# 2. INITIALIZE SERVICES VIA CONFIG
# -----------------------------------------------------------------------------
# Initialize Cloudinary
if CONFIG["CLOUDINARY_CLOUD_NAME"] and CONFIG["CLOUDINARY_API_KEY"] and CONFIG["CLOUDINARY_API_SECRET"]:
    cloudinary.config(
        cloud_name=CONFIG["CLOUDINARY_CLOUD_NAME"],
        api_key=CONFIG["CLOUDINARY_API_KEY"],
        api_secret=CONFIG["CLOUDINARY_API_SECRET"],
        secure=True
    )
elif os.environ.get('CLOUDINARY_URL'):
    cloudinary.config(cloudinary_url=os.environ.get('CLOUDINARY_URL'))

# Establish MongoDB Connection
@st.cache_resource
def init_mongo(uri):
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        client.server_info()  # Test connection health
        return client
    except Exception as e:
        st.error(f"❌ MongoDB Connection failed: {e}")
        return None

client = init_mongo(CONFIG["MONGO_URI"])

if client:
    db = client[CONFIG["DB_NAME"]] 
    collection = db[CONFIG["COLLECTION_NAME"]]
else:
    collection = None

# -----------------------------------------------------------------------------
# 3. MAIN APPLICATION INTERFACE
# -----------------------------------------------------------------------------
st.title(" 🖼️ Cloudinary & MongoDB Image Studio")
st.markdown("Query existing asset records from **MongoDB**, and apply real-time on-the-fly transformations using **Cloudinary URLs**.")

# Setup clean tabs layout
tabs = st.tabs(["✨ Asset Workspace", "📤 Upload New Asset", "📋 View Database Records"])

# -----------------------------------------------------------------------------
# TAB 1: ASSET WORKSPACE & MANIPULATION
# -----------------------------------------------------------------------------
with tabs[0]:
    st.subheader("Query & Manipulate Image Asset")
    
    if collection is not None:
        try:
            records = list(collection.find({}, {"public_id": 1, "title": 1, "_id": 0}))
            
            if records:
                asset_options = {f"{r.get('title', 'Untitled')} ({r['public_id']})": r['public_id'] for r in records}
                selected_label = st.selectbox("Select an Image Asset from MongoDB:", list(asset_options.keys()))
                selected_public_id = asset_options[selected_label]
                
                img_metadata = collection.find_one({"public_id": selected_public_id})
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.markdown("### ⚙️ Transformation Controls")
                    
                    crop_mode = st.selectbox("Crop Mode", ["fill", "scale", "fit", "thumb", "pad"])
                    width = st.slider("Width (px)", min_value=100, max_value=1200, value=600, step=50)
                    height = st.slider("Height (px)", min_value=100, max_value=1200, value=400, step=50)
                    
                    effect = st.selectbox("Visual Effects", [
                        "none", "grayscale", "sepia", "blur:300", "vignette", 
                        "negate", "oil_paint:40", "pixelate:10", "cartoonify"
                    ])
                    
                    background = st.selectbox("Background Pad Color", ["none", "black", "white", "red", "blue"])
                    
                    transformation_list = [{"width": width, "height": height, "crop": crop_mode}]
                    
                    if effect != "none":
                        transformation_list.append({"effect": effect})
                    if background != "none" and crop_mode in ["pad", "fill"]:
                        transformation_list.append({"background": background})
                        
                with col2:
                    st.markdown("### 🌅 Live Dynamic Output")
                    try:
                        transformed_image = CloudinaryImage(selected_public_id)
                        transformed_url = transformed_image.build_url(transformation=transformation_list)
                        
                        st.image(transformed_url, caption="Mutated Transformation Output", use_container_width=True)
                        st.code(transformed_url, language="text")
                    except Exception as cloud_err:
                        st.error(f"Cloudinary rendering issue: {cloud_err}")
                        
                with st.expander("🗄️ Stored MongoDB Metadata Document"):
                    st.json(str(img_metadata))
            else:
                st.warning("No records found in MongoDB. Upload an asset to get started.")
        except Exception as query_err:
            st.error(f"Error querying records: {query_err}")
    else:
        st.error("Could not link application layers. Verify your MongoDB configuration string settings.")

# -----------------------------------------------------------------------------
# TAB 2: UPLOAD ASSET & SAVE METADATA
# -----------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Upload Image to Cloudinary & Index in MongoDB")
    
    upload_title = st.text_input("Asset Title Reference", placeholder="e.g., Summer Banner")
    tags = st.text_input("Tags (comma separated)", placeholder="e.g., nature, background")
    uploaded_file = st.file_uploader("Choose an image file...", type=["jpg", "jpeg", "png", "webp"])
    
    if st.button("🚀 Upload and Index Asset"):
        if collection is None:
            st.error("Active database connection is required to index metadata.")
        elif not upload_title or not uploaded_file:
            st.error("Please provide both an asset title reference and a valid file payload.")
        else:
            with st.spinner("Uploading binary stream directly to Cloudinary target buckets..."):
                try:
                    upload_result = cloudinary.uploader.upload(
                        uploaded_file,
                        folder=f"{CONFIG['DB_NAME']}/uploads",
                        tags=[t.strip() for t in tags.split(",") if t.strip()]
                    )
                    
                    metadata_payload = {
                        "title": upload_title,
                        "public_id": upload_result.get("public_id"),
                        "secure_url": upload_result.get("secure_url"),
                        "format": upload_result.get("format"),
                        "bytes": upload_result.get("bytes"),
                        "created_at": upload_result.get("created_at"),
                        "tags": upload_result.get("tags", [])
                    }
                    
                    collection.insert_one(metadata_payload)
                    st.success(f"🎉 '{upload_title}' successfully uploaded to Cloudinary and indexed in MongoDB!")
                    st.balloons()
                    
                except Exception as upload_err:
                    st.error(f"Upload Ingestion Pipeline failed: {upload_err}")

# -----------------------------------------------------------------------------
# TAB 3: VIEW DATABASE RECORDS
# -----------------------------------------------------------------------------
with tabs[2]:
    st.subheader("📋 MongoDB Metadata Records Index")
    if collection is not None:
        try:
            all_records = list(collection.find({}))
            if all_records:
                for doc in all_records:
                    with st.container(border=True):
                        st.markdown(f"#### 📄 {doc.get('title', 'Untitled Asset')}")
                        st.markdown(f"**Public ID:** `{doc.get('public_id')}`")
                        st.markdown(f"**Direct URL Link:** [Open Resource]({doc.get('secure_url')})")
            else:
                st.info("No documents present inside the collection database index.")
        except Exception as err:
            st.error(f"Failed to fetch records: {err}")
