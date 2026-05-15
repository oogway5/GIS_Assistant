import streamlit as st
import google.generativeai as genai
from groq import Groq
from openai import OpenAI
from PIL import Image
import os
import json

# ─────────────────────────────────────────
# PAGE CONFIG & CONSTANTS
# ─────────────────────────────────────────
APP_TITLE = "🌍 Remote Sensing GIS Assistant"
APP_ICON = "🛰️"

st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")

# Pre-defined Prompts & Personas
DEFAULT_SYSTEM_PROMPT = (
    "You are a remote sensing analyst specializing in satellite imagery analysis. "
    "Your role is to help GIS engineers interpret optical and multispectral imagery, "
    "identify land cover types, and suggest appropriate band combinations for analysis. "
    "Provide highly technical insights and always cite relevant EPSG codes when projections are discussed."
)

PRESET_PROMPTS = [
    "Analyze this satellite image for land cover types.",
    "What is the best band combination for analyzing vegetation health?",
    "Suggest a workflow to monitor urban expansion over 5 years.",
    "Explain the difference between Sentinel-2 and Landsat 8 for crop monitoring."
]

MODELS = {
    "Gemini 2.5 Flash (Multimodal/Fast)": {"provider": "gemini", "id": "gemini-2.5-flash"},
    "Gemini 2.5 Pro (Multimodal/Smart)": {"provider": "gemini", "id": "gemini-2.5-pro"},
    "Groq: Llama 3.3 70B (Text/Fast)": {"provider": "groq", "id": "llama-3.3-70b-versatile"},
    "OpenRouter: Llama 3.3 70B (Text/Free)": {"provider": "openrouter", "id": "meta-llama/llama-3.3-70b-instruct:free"}
}

# ─────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings & Providers")

    # API Keys
    with st.expander("🔑 API Keys", expanded=True):
        gemini_key = st.text_input("Gemini API Key", type="password", value=os.environ.get("GOOGLE_API_KEY", ""))
        groq_key = st.text_input("Groq API Key", type="password", value=os.environ.get("GROQ_API_KEY", ""))
        openrouter_key = st.text_input("OpenRouter API Key", type="password", value=os.environ.get("OPENROUTER_API_KEY", ""))

    # Model & Parameters
    st.subheader("🧠 Model Configuration")
    model_label = st.selectbox("Select Model", list(MODELS.keys()))
    selected_model = MODELS[model_label]
    
    temperature = st.slider("Temperature", 0.0, 2.0, 0.3, 0.1, help="Lower = strict, Higher = creative")
    
    json_mode = st.toggle("📄 Force JSON Output", value=False, help="Forces the model to return valid JSON only")

    st.subheader("🎭 Persona (System Prompt)")
    system_prompt = st.text_area("System Instructions", value=DEFAULT_SYSTEM_PROMPT, height=200)

    st.subheader("⚡ Quick Prompts")
    selected_preset = st.selectbox("Choose a preset question:", [""] + PRESET_PROMPTS)

    st.markdown("---")
    
    # Export & Clear Chat
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.processed_preset = selected_preset  
            if "current_image" in st.session_state:
                del st.session_state.current_image
            st.rerun()
            
    with col2:
        # Export logic
        if "messages" in st.session_state and len(st.session_state.messages) > 0:
            export_text = "# Chat Export\n\n"
            for msg in st.session_state.messages:
                export_text += f"**{msg['role'].capitalize()}**:\n{msg['content']}\n\n---\n\n"
            st.download_button(
                label="📥 Export Chat",
                data=export_text,
                file_name="gis_analysis_chat.md",
                mime="text/markdown",
                use_container_width=True
            )

# ─────────────────────────────────────────
# MAIN INTERFACE
# ─────────────────────────────────────────
st.title(APP_TITLE)
st.caption("Advanced AI Assistant for GIS Engineers — Supports Text & Satellite Imagery (Gemini)")

# Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "processed_preset" not in st.session_state:
    st.session_state.processed_preset = None

# Top Section: Image Upload & Token Counter Placeholder
top_col1, top_col2 = st.columns([3, 1])

with top_col1:
    uploaded_file = st.file_uploader("📸 Upload Satellite Imagery (PNG/JPG/JPEG)", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.session_state.current_image = image
        with st.expander("👁️ View Uploaded Image", expanded=False):
            st.image(image, caption="Satellite Image Ready for Analysis", use_container_width=True)

with top_col2:
    # Basic token approximation (1 word ~ 1.3 tokens)
    total_words = sum(len(str(m['content']).split()) for m in st.session_state.messages)
    approx_tokens = int(total_words * 1.3)
    st.metric(label="🔢 Approx. Session Tokens", value=approx_tokens)

st.markdown("---")

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Determine the prompt (either from input or preset)
chat_input_val = st.chat_input("Ask a remote sensing or GIS question...")
prompt = None

if chat_input_val:
    prompt = chat_input_val
    st.session_state.processed_preset = None  
elif selected_preset and selected_preset != st.session_state.processed_preset:
    prompt = selected_preset
    st.session_state.processed_preset = selected_preset

# ─────────────────────────────────────────
# CHAT LOGIC & API ROUTING
# ─────────────────────────────────────────
if prompt:
    # 1. Validation
    if selected_model["provider"] == "gemini" and not gemini_key:
        st.error("⚠️ Please enter your Gemini API Key in the sidebar.")
        st.stop()
    if selected_model["provider"] == "groq" and not groq_key:
        st.error("⚠️ Please enter your Groq API Key in the sidebar.")
        st.stop()
    if selected_model["provider"] == "openrouter" and not openrouter_key:
        st.error("⚠️ Please enter your OpenRouter API Key in the sidebar.")
        st.stop()
        
    if "current_image" in st.session_state and selected_model["provider"] != "gemini":
        st.warning("⚠️ The selected model does not support image analysis. Only Gemini is multimodal in this setup. The image will be ignored.")

    # 2. Append and display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # 3. Process API Call based on provider
    with st.chat_message("assistant"):
        try:
            # ─── GEMINI ─────────────────────────────────────────
            if selected_model["provider"] == "gemini":
                genai.configure(api_key=gemini_key)
                
                # Combine System Prompt + JSON requirement if needed
                final_system_prompt = system_prompt
                if json_mode:
                    final_system_prompt += "\n\nIMPORTANT: Return ONLY valid JSON format."

                model = genai.GenerativeModel(
                    selected_model["id"], 
                    system_instruction=final_system_prompt
                )
                
                # Prepare contents
                contents = [prompt]
                if "current_image" in st.session_state:
                    contents.append(st.session_state.current_image)
                    
                response = model.generate_content(
                    contents, 
                    stream=True,
                    generation_config=genai.types.GenerationConfig(
                        temperature=temperature,
                        response_mime_type="application/json" if json_mode else "text/plain"
                    )
                )
                full_response = st.write_stream(chunk.text for chunk in response)

            # ─── GROQ ─────────────────────────────────────────
            elif selected_model["provider"] == "groq":
                client = Groq(api_key=groq_key)
                messages = [{"role": "system", "content": system_prompt}]
                
                if json_mode:
                    messages[0]["content"] += "\n\nIMPORTANT: Return ONLY valid JSON format."
                
                # Format history for Groq
                for m in st.session_state.messages[:-1]:
                    messages.append({"role": "assistant" if m["role"] == "assistant" else "user", "content": str(m["content"])})
                
                messages.append({"role": "user", "content": prompt})
                
                response = client.chat.completions.create(
                    model=selected_model["id"],
                    messages=messages,
                    temperature=temperature,
                    stream=True,
                    response_format={"type": "json_object"} if json_mode else None
                )
                
                def groq_generator():
                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                            
                full_response = st.write_stream(groq_generator())

            # ─── OPENROUTER ─────────────────────────────────────────
            elif selected_model["provider"] == "openrouter":
                client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_key)
                messages = [{"role": "system", "content": system_prompt}]
                
                if json_mode:
                    messages[0]["content"] += "\n\nIMPORTANT: Return ONLY valid JSON format."
                
                for m in st.session_state.messages[:-1]:
                    messages.append({"role": "assistant" if m["role"] == "assistant" else "user", "content": str(m["content"])})
                
                messages.append({"role": "user", "content": prompt})
                
                response = client.chat.completions.create(
                    model=selected_model["id"],
                    messages=messages,
                    temperature=temperature,
                    stream=True
                )
                
                def openrouter_generator():
                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                            
                full_response = st.write_stream(openrouter_generator())

            # 4. Save response to history
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # Auto-rerun to update token count
            st.rerun()

        except Exception as e:
            st.error(f"⚠️ Error from {selected_model['provider'].capitalize()} API: {str(e)}")