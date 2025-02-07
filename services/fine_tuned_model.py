# import uvicorn
# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles  
# import os
# import textwrap
# import re
# import base64
# import io
# import matplotlib.pyplot as plt
# from datetime import datetime
# import logging
# from pymongo import MongoClient
# from bson import ObjectId
# from openai import OpenAI
# from config import OPENAI_API_KEY
# from models.request_models import FineTuneModelRequest, FineTuneModelResponse


# # Constants
# RESULTS_FOLDER = "static"  # Changed to static for FastAPI static file serving
# PLOTS_FOLDER = "plots"
# STATIC_URL_BASE = "http://127.0.0.1:8000/static"  # Base URL for static files

# # Initialize MongoDB Client
# client = MongoClient("mongodb+srv://chandu:6264@chanduretineni.zfbcc.mongodb.net/?retryWrites=true&w=majority&appName=ChanduRetineni")
# db = client["Kuizlo"]
# essays_collection = db["essays"]

# # Configure OpenAI Client
# openai_client = OpenAI(api_key=OPENAI_API_KEY)


# # Configure OpenAI Client
# openai_client = OpenAI(api_key=OPENAI_API_KEY)

# # Configure Logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# class EssayProcessor:
#     def __init__(self):
#         self.html_template = """
#         <!DOCTYPE html>
#         <html>
#         <head>
#             <title>{title}</title>
#             <style>
#                 body {{
#                     padding: 30px;
#                     line-height: 1.8;
#                     font-family: 'Segoe UI', Arial, sans-serif;
#                     color: #2c3e50;
#                     background-color: #f5f6fa;
#                     max-width: 1200px;
#                     margin: 0 auto;
#                 }}
#                 h1 {{
#                     color: #2c3e50;
#                     border-bottom: 3px solid #3498db;
#                     padding-bottom: 15px;
#                     margin-bottom: 30px;
#                     font-size: 2.2em;
#                 }}
#                 .section {{
#                     background: white;
#                     padding: 25px;
#                     border-radius: 12px;
#                     box-shadow: 0 4px 6px rgba(0,0,0,0.1);
#                     margin-bottom: 25px;
#                 }}
#                 .section-title {{
#                     color: #2c3e50;
#                     font-weight: 600;
#                     font-size: 1.4em;
#                     padding-bottom: 10px;
#                     margin-bottom: 15px;
#                     border-bottom: 2px solid #e9ecef;
#                 }}
#                 .plot-container {{
#                     text-align: center;
#                     margin: 20px 0;
#                     padding: 15px;
#                     background: #f8f9fa;
#                     border-radius: 8px;
#                 }}
#                 .plot-container img {{
#                     max-width: 100%;
#                     height: auto;
#                     width: auto;
#                     max-height: 600px;
#                     border-radius: 8px;
#                     box-shadow: 0 2px 4px rgba(0,0,0,0.1);
#                 }}
#                 pre {{
#                     background-color: #f8f9fa;
#                     padding: 20px;
#                     border-radius: 8px;
#                     overflow-x: auto;
#                     border: 1px solid #e9ecef;
#                     font-family: 'Consolas', monospace;
#                     font-size: 14px;
#                     line-height: 1.6;
#                 }}
#                 table {{
#                     width: 100%;
#                     border-collapse: collapse;
#                     margin: 15px 0;
#                 }}
#                 th, td {{
#                     border: 1px solid #e9ecef;
#                     padding: 12px;
#                     text-align: left;
#                 }}
#                 th {{
#                     background-color: #f8f9fa;
#                     font-weight: 600;
#                 }}
#                 .error {{
#                     color: #dc3545;
#                     padding: 10px;
#                     background-color: #f8d7da;
#                     border-radius: 4px;
#                     margin-top: 10px;
#                 }}
#             </style>
#         </head>
#         <body>
#             <h1>{title}</h1>
#             {content}
#         </body>
#         </html>
#         """

#     # def execute_python_code(self, code, plot_counter):
#     #     """Execute Python code and save plot with enhanced settings."""
#     #     try:
#     #         plt.close('all')  # Clear previous plots
#     #         buffer = io.BytesIO()
            
#     #         # Create local namespace
#     #         local_namespace = {}
            
#     #         # Fix the style configuration
#     #         style_config = "plt.rcParams['figure.figsize'] = [10, 6]\n"
#     #         style_config += "plt.rcParams['font.size'] = 10\n"
#     #         style_config += "plt.rcParams['axes.labelsize'] = 12\n"
#     #         style_config += "plt.rcParams['axes.titlesize'] = 14\n"
            
#     #         # Dedent the input code to remove any leading whitespace
#     #         code = textwrap.dedent(code)
            
#     #         # Execute style config and main code
#     #         exec(style_config, globals(), local_namespace)
#     #         exec(code, globals(), local_namespace)
            
#     #         # Save the plot
#     #         plt.savefig(buffer, format='png', bbox_inches='tight', dpi=300, 
#     #                    facecolor='white', edgecolor='none')
#     #         buffer.seek(0)
#     #         plot_data = base64.b64encode(buffer.getvalue()).decode()
#     #         buffer.close()
            
#     #         # Use formatted counter in filename
#     #         plot_filename = f"plot_{plot_counter:03d}.png"
#     #         plot_url = self.save_plot_to_file(plot_data, plot_filename)
            
#     #         if plot_url:
#     #             return {'code': code, 'plot_path': plot_url, 'plot_data': plot_data}
#     #         else:
#     #             return {'code': code, 'error': 'Failed to save plot'}
                
#     #     except Exception as error:
#     #         logging.error(f"Error executing code: {error}")
#     #         return {'code': code, 'error': str(error)}

#     def execute_python_code(self, code, plot_counter):
#         """Execute Python code and save plot, skipping plt.show()."""
#         try:
#             plt.close('all')  # Clear previous plots
#             buffer = io.BytesIO()

#             # Create local namespace
#             local_namespace = {}

#             # Patch plt.show() to prevent display interruption
#             patched_code = (
#                 "import matplotlib.pyplot as plt\n"
#                 "plt.show = lambda: None\n"  # Override plt.show()
#             ) + textwrap.dedent(code)

#             # Execute the patched code
#             exec(patched_code, globals(), local_namespace)

#             # Save the plot
#             plt.savefig(buffer, format='png', bbox_inches='tight', dpi=300, 
#                         facecolor='white', edgecolor='none')
#             plt.close("all")  # Close the plot after saving
#             buffer.seek(0)  # Ensure buffer points to the start
#             plot_data = base64.b64encode(buffer.getvalue()).decode()
#             buffer.close()

#             # Use formatted counter in filename
#             plot_filename = f"plot_{plot_counter:03d}.png"
#             plot_url = self.save_plot_to_file(plot_data, plot_filename)

#             if plot_url:
#                 return {'code': code, 'plot_path': plot_url, 'plot_data': plot_data}
#             else:
#                 return {'code': code, 'error': 'Failed to save plot'}

#         except Exception as error:
#             logging.error(f"Error executing code: {error}")
#             return {'code': code, 'error': str(error)}

#     def save_plot_to_file(self, plot_data, file_name):
#         """Save plot image to static directory and return static URL."""
#         plots_dir = os.path.join(RESULTS_FOLDER, PLOTS_FOLDER)
#         os.makedirs(plots_dir, exist_ok=True)
#         file_path = os.path.join(plots_dir, file_name)
        
#         try:
#             with open(file_path, "wb") as file:
#                 file.write(base64.b64decode(plot_data))
#             # Return static URL for the plot
#             return f"/static/{PLOTS_FOLDER}/{file_name}"  # Changed to relative URL
#         except Exception as e:
#             logging.error(f"Error saving plot: {e}")
#             return None

#     def parse_essay_sections(self, essay_text):
#         """Extract and format sections from essay text with improved parsing."""
#         sections = []
#         lines = essay_text.split('\n')
#         current_section = []
#         current_title = None
#         in_code_block = False
#         code_lines = []
        
#         i = 0
#         while i < len(lines):
#             line = lines[i].strip()
            
#             # Handle markdown table at the beginning
#             if line.startswith('|') and not current_title:
#                 table_lines = []
#                 while i < len(lines) and lines[i].strip().startswith('|'):
#                     table_lines.append(lines[i])
#                     i += 1
#                 if table_lines:
#                     sections.append({
#                         'title': 'Article Details',
#                         'content': '\n'.join(table_lines),
#                         'type': 'table'
#                     })
#                 continue
                
#             # Handle section titles
#             if line.startswith('**') and line.endswith('**'):
#                 if current_section and not in_code_block:
#                     sections.append({
#                         'title': current_title,
#                         'content': '\n'.join(current_section),
#                         'type': 'text'
#                     })
#                 current_section = []
#                 current_title = line.strip('*').strip()
#                 i += 1
#                 continue
                
#             # Handle code blocks
#             if line.startswith('```python'):
#                 in_code_block = True
#                 code_lines = []
#                 i += 1
#                 while i < len(lines) and not lines[i].strip().startswith('```'):
#                     code_lines.append(lines[i])
#                     i += 1
#                 if code_lines:
#                     sections.append({
#                         'title': current_title,
#                         'content': '\n'.join(code_lines),
#                         'type': 'code'
#                     })
#                 in_code_block = False
#                 current_section = []
#                 i += 1
#                 continue
                
#             # Regular content
#             if not in_code_block:
#                 current_section.append(line)
#             i += 1
            
#         # Add the last section if exists
#         if current_section:
#             sections.append({
#                 'title': current_title,
#                 'content': '\n'.join(current_section),
#                 'type': 'text'
#             })
            
#         return sections

#     def process_python_sections(self, sections, plot_counter):
#         """Process code blocks with enhanced plot handling."""
#         plots_data = []
#         html_sections = []
#         plot_count = 1
        
#         for section in sections:
#             if section['type'] == 'table':
#                 html_sections.append(
#                     f'<div class="section"><div class="section-title">{section["title"]}</div>'
#                     f'<div class="table-container">{section["content"]}</div></div>'
#                 )
#             elif section['type'] == 'code':
#                 plot_data = self.execute_python_code(section['content'], plot_count)
#                 plots_data.append(plot_data)
                
#                 plot_html = f'<div class="section">'
#                 if section['title']:
#                     plot_html += f'<div class="section-title">{section["title"]}</div>'
#                 plot_html += f'<pre>{plot_data["code"]}</pre>'
#                 if 'plot_path' in plot_data:
#                     plot_html += (
#                         f'<div class="plot-container">'
#                         f'<img src="{plot_data["plot_path"]}" alt="Plot {plot_count}" '
#                         f'loading="lazy">'
#                         f'</div>'
#                     )
#                 elif 'error' in plot_data:
#                     plot_html += f'<p class="error">Error: {plot_data["error"]}</p>'
#                 plot_html += '</div>'
#                 html_sections.append(plot_html)
#                 plot_count += 1
#             else:
#                 if section['content'].strip():
#                     html_sections.append(
#                         f'<div class="section">'
#                         f'<div class="section-title">{section["title"]}</div>'
#                         f'<div class="content">{section["content"]}</div>'
#                         f'</div>'
#                     )

#         return html_sections, plots_data

#     def create_directories(self):
#         """Create directories for results and plots."""
#         os.makedirs(RESULTS_FOLDER, exist_ok=True)
#         os.makedirs(os.path.join(RESULTS_FOLDER, PLOTS_FOLDER), exist_ok=True)


#     def create_html(self, title, content):
#         """Generate full HTML from title and content."""
#         return self.html_template.format(title=title, content='\n'.join(content))

#     def save_essay_to_db(self, topic, essay_text, plots, html_path):
#         """Save essay details to MongoDB."""
#         essay_id = essays_collection.insert_one({
#             'topic': topic,
#             'content': essay_text,
#             'plots': plots,
#             'created_at': datetime.now(),
#             'html_path': html_path
#         }).inserted_id
#         return str(essay_id)

#     def save_html_to_file(self, topic, content):
#         """Save HTML content to a file and return file path."""
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         safe_topic = re.sub(r'[^\w\s-]', '', topic).replace(' ', '_')
#         file_name = f"{safe_topic}_{timestamp}.html"
#         file_path = os.path.join(RESULTS_FOLDER, file_name)
        
#         with open(file_path, "w", encoding="utf-8") as file:
#             file.write(content)
        
#         return file_path

#     def process_essay(self, essay_text, topic):
#         """Main function to process essay and store required components."""
#         self.create_directories()
#         sections = self.parse_essay_sections(essay_text)
#         html_content, plots_data = self.process_python_sections(sections, plot_counter=1)
#         final_html = self.create_html(topic, html_content)
#         essay_id = self.save_essay_to_db(topic, essay_text, plots_data, final_html)
#         file_path = self.save_html_to_file(topic, final_html)

#         return {'essay_id': essay_id, 'file_path': file_path, 'html_content': final_html}

# async def prompt_fine_tuned_model(prompt_text, topic):
#     """Prompt the fine-tuned model to generate an essay."""
#     try:
#         response = openai_client.chat.completions.create(
#             model="ft:gpt-4o-mini-2024-08-06:kuizlo::Am1frrxs",
#             messages=[
#                 {"role": "system", "content": """You are an IB Economics Internal Assessment (IA) essay generator..."""},  # Condensed for brevity
#                 {"role": "user", "content": str(prompt_text)}
#             ],
#             max_tokens=4000,
#             temperature=0.7
#         )
        
#         essay_txt = response.choices[0].message.content
#         processor = EssayProcessor()
#         ex_essay_txt = """Here's an IA essay based on the provided article details:
# | Article | Article's URL | Date the Article was Published | Date of Commentary | Word Count | Section of Syllabus | Key Concept |
# |---------|---------------|-------------------------------|--------------------|------------|--------------------|-------------|
# | U.S. Stock Index Futures Edge Higher | Not Provided | January 3, 2025 | October 5, 2023 | 784 | Macroeconomics | Inflation, Monetary Policy, Market Expectations |
# **Introduction**
# The article discusses fluctuations in U.S. **stock indices** amid uncertainties surrounding policy changes under the incoming Trump administration. The prospect of reduced corporate taxes and eased regulations has bolstered investor confidence, pushing indices higher. However, concerns about potential **inflation** and monetary policy adjustments have created volatility. The **Federal Reserve** is expected to lower interest rates to maintain economic stability. This situation illustrates macroeconomic dynamics involving **market expectations**, **fiscal policies**, and **monetary interventions**, reflecting their interconnected impact on national output and inflation.
# **Diagram**
# ```python
# import matplotlib.pyplot as plt
# # Data
# interest_rates = [5.0, 4.5, 4.0, 3.5]
# GDP_growth = [1.5, 2.0, 2.5, 3.0]
# inflation = [2.5, 3.0, 2.7, 2.2]
# # Plot
# fig, ax1 = plt.subplots(figsize=(10, 6))
# # Plotting GDP growth
# ax1.set_xlabel('Interest Rates (%)')
# ax1.set_ylabel('GDP Growth (%)', color='tab:blue')
# ax1.plot(interest_rates, GDP_growth, 'o-', color='tab:blue', label='GDP Growth')
# ax1.tick_params(axis='y', labelcolor='tab:blue')
# # Secondary y-axis for inflation
# ax2 = ax1.twinx()
# ax2.set_ylabel('Inflation (%)', color='tab:red')
# ax2.plot(interest_rates, inflation, 's-', color='tab:red', label='Inflation')
# ax2.tick_params(axis='y', labelcolor='tab:red')
# # Title and grid
# plt.title('Impact of Interest Rates on GDP Growth and Inflation')
# fig.tight_layout()
# plt.grid(True)
# ```
# **Analysis**
# The diagram illustrates the relationship between **interest rates**, **GDP growth**, and **inflation**. As interest rates decrease, GDP growth increases, reflecting a stimulative effect on the economy. Conversely, lower rates can lead to higher inflation, necessitating careful management by the **Federal Reserve**. In the article, expectations of a 50 basis point rate reduction aim to counteract uncertainties and support economic resilience. However, overstimulation risks exacerbating inflation, which could deter long-term growth. The trade-off highlights the delicate balance between fostering economic expansion and maintaining price stability.
# **Evaluation**
# **Long-term vs. Short-term Effects**
# **Short-term**
# Lowering interest rates boosts economic activity by reducing borrowing costs, encouraging investment, and increasing consumption.
# **Long-term**
# Prolonged low rates may lead to inflationary pressures, reducing purchasing power and necessitating stricter monetary policies.
# **Assumptions**
# The analysis assumes that rate cuts directly translate into increased investments and spending. However, uncertainties around fiscal policies may dampen business confidence, limiting the effectiveness of monetary interventions.
# **Stakeholders**
# **Consumers**
# Benefit from lower borrowing costs but face risks of rising inflation eroding savings.
# **Businesses**
# Reduced interest rates lower financing costs, supporting expansion. However, regulatory uncertainties may hinder investment decisions.
# **Government**
# Must balance fiscal policies with monetary actions to sustain economic stability and prevent overheating.
# **Society**
# Widespread economic growth fosters job creation and income equality but risks inflationary pressures affecting low-income households disproportionately.
# **Practicality**
# While interest rate reductions provide immediate economic relief, their long-term success depends on complementary fiscal policies that address structural uncertainties.
# **Conclusion**
# The article underscores the interplay between fiscal and monetary policies in managing economic stability. While lowering interest rates offers short-term benefits, addressing structural uncertainties under the new administration is crucial for sustainable growth. Effective policy coordination can mitigate inflationary risks while maximizing economic resilience. Engaging stakeholders and ensuring transparent communication will enhance confidence, fostering a stable macroeconomic environment.
# **References**
# - Johann M, “U.S. Stock Index Futures Edge Higher.” Reuters News, January 3, 2025.

# """
#         results = processor.process_essay(essay_txt, topic)

#         return FineTuneModelResponse(
#             essay_id=results['essay_id'],
#             model_output=essay_txt,
#             html_content=results['html_content'],
#             file_path=results['file_path'],
#         )
        
#     except Exception as e:
#         logging.error(f"Unexpected Error: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
