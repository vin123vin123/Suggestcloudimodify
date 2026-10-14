import streamlit as st
import pymongo
from cloudinary import CloudinaryImage
import cloudinary.uploader
import cloudinary.api
import os

# -----------------------------------------------------------------------------
# 1. DATABASE & CLOUD CONFIGURATION
# -----------------------------------------------------------------------------
# Replace these strings or configure via Streamlit Secrets / Environment Variables
MONGO_URI = st.sidebar.text_input("MongoDB Connection URI", value="mongodb://localhost:27017/", type="password")
DB_NAME = st.sidebar.text_input("MongoDB Database Name", value="image_gallery")
COLLECTION_NAME = st.sidebar.text_input("MongoDB Collection Name", value="metadata")

st.sidebar.markdown("---")
CLOUDINARY_CLOUD_NAME = st.sidebar.text_input("Cloudinary Cloud Name", value="")
CLOUDINARY_API_KEY = st.sidebar.text_input("Cloudinary API Key", value="", type="password")
CLOUDINARY_API_SECRET = st.sidebar.text_input("Cloudinary API Secret", value="", type="password")

# Initialize Cloudinary Configuration dynamically if provided
if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True
    )

CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL')
if CLOUDINARY_URL:
    cloudinary.config(cloudinary_url=CLOUDINARY_URL)
    print("cloudi... con...estblsh..")
# Establish MongoDB Connection
@st.cache_resource
def init_mongo(uri):
    try:
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=2000)
        # Test connection
        client.server_info()
        return client
    except Exception as e:
        st.sidebar.error(f"MongoDB Connection failed: {e}")
        return None

client = init_mongo(MONGO_URI)
db = client['cloudi'] if client else None
collection = db.imagescloudi if db is not None else None

# -----------------------------------------------------------------------------
# 2. MAIN APPLICATION INTERFACE
# -----------------------------------------------------------------------------
st.title("🖼️ Cloudinary & MongoDB Image Studio")
st.markdown("Query existing asset records from **MongoDB**, and apply real-time on-the-fly transformations using **Cloudinary URLs**.")

if not CLOUDINARY_CLOUD_NAME:
    st.info("Please fill in your Cloudinary configurations in the sidebar to start mutating images.")

# Layout: Split page into Sidebar Management and Workspace
tabs = st.tabs(["✨ Asset Workspace", "📤 Upload New Asset", "📋 View Database Records"])

# -----------------------------------------------------------------------------
# TAB 1: ASSET WORKSPACE & MANIPULATION
# -----------------------------------------------------------------------------
with tabs[0]:
    st.subheader("Query & Manipulate Image Asset")
    
    if collection is not None:
        try:
            # Fetch available asset options from DB to select from
            records = list(collection.find({}, {"public_id": 1, "title": 1, "_id": 0}))
            
            if records:
                asset_options = {f"{r.get('title', 'Untitled')} ({r['public_id']})": r['public_id'] for r in records}
                selected_label = st.selectbox("Select an Image Asset from MongoDB:", list(asset_options.keys()))
                selected_public_id = asset_options[selected_label]
                
                # Fetch complete document from MongoDB
                img_metadata = collection.find_one({"public_id": selected_public_id})
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.markdown("### ⚙️ Transformation Controls")
                    
                    # Aspect Ratio & Crop options
                    crop_mode = st.selectbox("Crop Mode", ["fill", "scale", "fit", "thumb", "pad"])
                    width = st.slider("Width (px)", min_value=100, max_value=1200, value=600, step=50)
                    height = st.slider("Height (px)", min_value=100, max_value=1200, value=400, step=50)
                    
                    # Creative Effects
                    effect = st.selectbox("Visual Effects", [
                        "none", "grayscale", "sepia", "blur:300", "vignette", 
                        "negate", "oil_paint:40", "pixelate:10", "cartoonify"
                    ])
                    
                    # Background manipulation for padding
                    background = st.selectbox("Background Pad Color", ["none", "black", "white", "red", "blue"])
                    
                    # Formulate transformation list dynamically based on parameters
                    transformation_list = [
                        {"width": width, "height": height, "crop": crop_mode}
                    ]
                    
                    if effect != "none":
                        transformation_list.append({"effect": effect})
                    if background != "none" and crop_mode in ["pad", "fill"]:
                        transformation_list.append({"background": background})
                        
                with col2:
                    st.markdown("### 🌅 Live Dynamic Output")
                    
                    # Generate secure variant link with Cloudinary URL SDK
                    if CLOUDINARY_CLOUD_NAME:
                        try:
                            transformed_image = CloudinaryImage(selected_public_id)
                            transformed_url = transformed_image.build_url(transformation=transformation_list)
                            
                            st.image(transformed_url, caption=f"Mutated Output URL: {selected_public_id}", use_container_width=True)
                            st.code(transformed_url, language="text")
                        except Exception as cloud_err:
                            st.error(f"Cloudinary rendering issue: {cloud_err}")
                    else:
                        st.warning("Provide Cloudinary credentials to generate your preview image link.")
                        
                # Show record provenance data
                with st.expander("🗄️ Stored MongoDB Metadata Document"):
                    st.json(str(img_metadata))
            else:
                st.warning("No records found in MongoDB. Upload an asset to get started.")
        except Exception as query_err:
            st.error(f"Error querying records: {query_err}")
    else:
        st.error("Establish a database connection via the sidebar menu first.")

# -----------------------------------------------------------------------------
# TAB 2: UPLOAD ASSET & SAVE METADATA
# -----------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Upload Image to Cloudinary & Index in MongoDB")
    
    upload_title = st.text_input("Asset Title Reference", placeholder="e.g., Summer Banner")
    tags = st.text_input("Tags (comma separated)", placeholder="e.g., nature, background")
    uploaded_file = st.file_uploader("Choose an image file...", type=["jpg", "jpeg", "png", "webp"])
    
    if st.button("🚀 Upload and Index Asset"):
        if not CLOUDINARY_CLOUD_NAME or collection is None:
            st.error("Both Cloudinary configurations and MongoDB connections are strictly required to upload files.")
        elif not upload_title or not uploaded_file:
            st.error("Please provide both an asset title reference and a valid file payload.")
        else:
            with st.spinner("Processing file streaming..."):
                try:
                    # Upload byte stream explicitly directly to Cloudinary storage buckets
                    upload_result = cloudinary.uploader.upload(
                        uploaded_file,
                        folder=f"{DB_NAME}/uploads",
                        tags=[t.strip() for t in tags.split(",") if t.strip()]
                    )
                    
                    # Extract valuable transaction parameters
                    metadata_payload = {
                        "title": upload_title,
                        "public_id": upload_result.get("public_id"),
                        "secure_url": upload_result.get("secure_url"),
                        "format": upload_result.get("format"),
                        "bytes": upload_result.get("bytes"),
                        "created_at": upload_result.get("created_at"),
                        "tags": upload_result.get("tags", [])
                    }
                    
                    # Atomic injection into MongoDB document layer
                    insert_res = collection.insert_one(metadata_payload)
                    
                    st.success(f"Successfully uploaded asset to Cloudinary and registered metadata entry in MongoDB!")
                    st.balloons()
                    st.json(metadata_payload)
                    
                except Exception as upload_err:
                    st.error(f"Transaction pipeline failed: {upload_err}")

# -----------------------------------------------------------------------------
# TAB 3: MANAGE RECORDS DIRECTLY
# -----------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Stored Document Context Layer")
    if collection is not None:
        try:
            all_records = list(collection.find({}))
            if all_records:
                for doc in all_records:
                    with st.container(border=True):
                        st.markdown(f"#### **{doc.get('title', 'Untitled')}** (`{doc.get('public_id')}`)")
                        st.markdown(f"**Original Cloudinary Resource String:** [{doc.get('secure_url')}]({doc.get('secure_url')})")
                        st.markdown(f"**Format:** `{doc.get('format')}` | **Size:** `{doc.get('bytes', 0) / 1024:.2f} KB`")
                        if st.button(f"🗑️ Delete Record", key=f"del_{doc.get('public_id')}"):
                            collection.delete_one({"public_id": doc.get('public_id')})
                            st.toast(f"Removed reference record {doc.get('public_id')}")
                            st.rerun()
            else:
                st.info("The selected collection data layer contains zero indexing documents.")
        except Exception as e:
            st.error(f"Error querying data tables: {e}")
    else:
        st.info("Connect your active cluster node to browse structural datasets.")
