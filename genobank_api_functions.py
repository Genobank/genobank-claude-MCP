import io
import base64
import qrcode
import asyncio
import json
import threading
import http.server
import socketserver
import httpx
import webbrowser
from typing import Any, Dict, Optional
from mcp.server.fastmcp import FastMCP

GENBANK_API_BASE = "https://genobank.app"
OPENCRAVAT_API_BASE = "https://cravat.genobank.app"

# GENBANK_API_BASE = "http://localhost:8081"
# OPENCRAVAT_API_BASE = "http://localhost:9091"


mcp = FastMCP("genobank_api_functions")

user_signature = None
server_instance = None

@mcp.tool()
async def mint_ip_job(
    receiver: str,
    job_id: str,
    biosample_serial: int,
    opencravat_version: str,
    num_unique_var: str,
    owner: str,
    submission_time: str,
    assembly: str,
    ip_asset: str = ""
) -> str:
    url = (
        f"{GENBANK_API_BASE}/mint_ipa_job?"
        f"receiver={receiver}"
        f"&job_id={job_id}"
        f"&biosample_serial={biosample_serial}"
        f"&opencravat_version={opencravat_version}"
        f"&num_unique_var={num_unique_var}"
        f"&owner={owner}"
        f"&submission_time={submission_time}"
        f"&assembly={assembly}"
        f"&ip_asset={ip_asset}"
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, timeout=10.0)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
    except Exception as e:
        return f"Error during Minting IP Job: {e}"
    
    return f"Success: {data}"


@mcp.tool()
async def start_signature_server() -> str:
    """
    Starts a local web server that allows the user to sign with MetaMask.
    Additionally, once started, the server automatically opens in the browser.
    
    return Please, visit http://localhost:8000
    """
    global user_signature, server_instance
    user_signature = None
    PORT = 8000
    
    html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>MetaMask Signature</title>
            <script src="https://cdn.jsdelivr.net/npm/web3@1.6.0/dist/web3.min.js"></script>
            <style>
                /* Reset and base styles */
                body, h1, p, button {
                    margin: 0;
                    padding: 0;
                }
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: #f4f6f8;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    color: #333;
                }
                /* Container for the card */
                .container {
                    background: #fff;
                    border-radius: 8px;
                    padding: 30px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    width: 100%;
                    max-width: 480px;
                    text-align: center;
                }
                h1 {
                    margin-bottom: 20px;
                    font-size: 24px;
                    color: #222;
                }
                p {
                    margin-bottom: 20px;
                    font-size: 16px;
                    line-height: 1.5;
                }
                /* Button styling */
                button {
                    background-color: #0579ce;
                    border: none;
                    color: #fff;
                    padding: 12px 20px;
                    font-size: 16px;
                    border-radius: 4px;
                    transition: background-color 0.3s ease;
                    cursor: pointer;
                    margin: 10px;
                }
                button:hover {
                    background-color: #0056b3;
                }
                button:disabled {
                    background-color: #6c757d;
                    cursor: not-allowed;
                }
                /* Status message styling */
                #status {
                    margin-top: 20px;
                    padding: 15px;
                    border-radius: 5px;
                    font-size: 14px;
                }
                .success {
                    background-color: #d4edda;
                    color: #155724;
                    border: 1px solid #c3e6cb;
                }
                .error {
                    background-color: #f8d7da;
                    color: #721c24;
                    border: 1px solid #f5c6cb;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Metamask signing process</h1>
                <img src="https://cdn.iconscout.com/icon/free/png-512/free-metamask-logo-icon-download-in-svg-png-gif-file-formats--browser-extension-chrome-logos-icons-2261817.png?f=webp&w=256" width=50>
                <p>To continue you must connect your wallet and sign your authorization.</p>
                <button id="connectAndSignButton">Connect & Sign with MetaMask</button>
                <div id="status"></div>
            </div>
            <script>
                const message = "I want to proceed";
                const statusDiv = document.getElementById('status');
                
                // Check if MetaMask is installed
                window.addEventListener('load', function() {
                    if (!window.ethereum) {
                        statusDiv.textContent = "MetaMask is not installed. Please install it to continue.";
                        statusDiv.className = "error";
                    }
                });
                
                // Connect and sign in a single flow
                document.getElementById('connectAndSignButton').addEventListener('click', async () => {
                    if (window.ethereum) {
                        try {
                            // Step 1: Connect
                            statusDiv.textContent = "Connecting to MetaMask...";
                            const accounts = await ethereum.request({ method: 'eth_requestAccounts' });
                            statusDiv.textContent = `Connected with account: ${accounts[0]}. Requesting signature...`;
                            
                            // Step 2: Sign
                            const signature = await ethereum.request({
                                method: 'personal_sign',
                                params: [message, accounts[0]],
                            });
                            
                            // Step 3: Send signature to server
                            statusDiv.textContent = "Sending signature to server...";
                            
                            fetch('/submit-signature', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ signature })
                            })
                            .then(response => response.text())
                            .then(data => {
                                statusDiv.textContent = "Signature received! This window will close automatically.";
                                statusDiv.className = "success";
                                
                                // Close the window after 2 seconds
                                setTimeout(() => {
                                    window.close();
                                }, 2000);
                            });
                        } catch (error) {
                            statusDiv.textContent = `Error: ${error.message}`;
                            statusDiv.className = "error";
                        }
                    }
                });
            </script>
        </body>
        </html>
    """
    
    class SigningHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(html_content.encode())
            
        def do_POST(self):
            global user_signature
            if self.path == '/submit-signature':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                post_json = json.loads(post_data.decode())
                
                user_signature = post_json.get('signature')
                
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Signature received")
    
    def run_server():
        global server_instance
        with socketserver.TCPServer(("", PORT), SigningHandler) as httpd:
            server_instance = httpd
            print(f"Server started at http://localhost:{PORT}")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                httpd.server_close()
    
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    webbrowser.open(f"http://localhost:{PORT}")
    return f"Browser automatically opened at http://localhost:{PORT}"


@mcp.tool()
async def stop_signature_server() -> str:
    """
    Stops the signature server if it's running.
    """
    global server_instance
    if server_instance:
        server_instance.shutdown()
        server_instance.server_close()
        server_instance = None
        return "Signature server successfully stopped."
    else:
        return "No signature server is currently running."


@mcp.tool()
async def check_signature_status() -> str:
    """
    Checks if the user has already signed with MetaMask.
    """
    global user_signature
    if user_signature:
        return f"Signature received: {user_signature[:10]}...{user_signature[-10:]}"
    else:
        return "No signature has been received yet. Please complete the signing process on the web page."


@mcp.tool()
async def mint_license_token(
    ip_asset: str,
    receiver: str,
) -> str:
    """
    Mints the license token using the signature provided by the user.
    """
    global user_signature
    if not user_signature:
        return "No signature has been received. Please use start_signature_server first and complete the signing process. Showing a link to redirect to 'http://localhost:8000/'"
    url = (
        f"{GENBANK_API_BASE}/mint_license_token?"
        f"ip_asset={ip_asset}"
        f"&receiver={receiver}"
        f"&user_signature={user_signature}"
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, timeout=10.0)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            user_signature = None
            return f"License Token successfully created: {data}"
    except Exception as e:
        return f"Error minting License Token: {e}"


@mcp.tool()
async def mint_license_token_flow(
    ip_asset: str,
    receiver: str,
) -> str:
    """
    Complete flow to mint a license token, including obtaining the signature.
    """
    server_result = await start_signature_server()
    progress_message = f"Starting signature process...\n{server_result}\n\nWaiting for signature completion..."
    global user_signature
    max_attempts = 60 
    attempt = 0
    
    while not user_signature and attempt < max_attempts:
        await asyncio.sleep(2) 
        attempt += 1
    
    if not user_signature:
        await stop_signature_server()
        return "Timeout reached. No signature was received. Please try again."
    
    progress_message += "\n\nSignature received! Processing license token minting..."
    mint_result = await mint_license_token(ip_asset, receiver)
    await stop_signature_server()
    return f"{progress_message}\n\n{mint_result}"





@mcp.tool()
async def get_ancestry_html_results() -> str:
    """
    Gets the ancestry results for a user.
    If no signature exists, it requests one through the signature server.
    
    return: Allways return the result in an HTML artifact preview
    """
    global user_signature
    
    if not user_signature:
        server_result = await start_signature_server()
        progress_message = f"Starting signature process...\n{server_result}\n\nWaiting for signature completion..."
        max_attempts = 60
        attempt = 0
        while not user_signature and attempt < max_attempts:
            await asyncio.sleep(2)
            attempt += 1
        if not user_signature:
            await stop_signature_server()
            return "Timeout reached. No signature was received. Please try again."
        await stop_signature_server()
        progress_message += "\n\nSignature received! Processing ancestry request..."
    else:
        progress_message = "Using existing signature for ancestry request..."
    
    url = f"{GENBANK_API_BASE}/api_somos_dao/get_results?user_signature={user_signature}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            html = get_html_ancestry_page_chart(data)    
            return f"open in an html preview artifact {html}"
    except Exception as e:
        return f"Error retrieving ancestry results: {e}"

def get_html_ancestry_page_chart(data):
    try:
        ancestry_data = data.get("data", {}).get("ancestry", {})
        filtered_data = {k: float(v) for k, v in ancestry_data.items() if float(v) > 0.0001}
        colors = [f"hsl({(i * 137) % 360}, 70%, 65%)" for i in range(len(filtered_data))]
        sorted_data = dict(sorted(filtered_data.items(), key=lambda x: float(x[1]), reverse=True))
        labels = list(sorted_data.keys())
        values = [float(v) * 100 for v in sorted_data.values()]  # Convert to percentages
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Ancestry Results</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.7.0/chart.min.js"></script>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #333;
                    text-align: center;
                }}
                .chart-container {{
                    position: relative;
                    height: 400px;
                    width: 100%;
                    margin: 20px auto;
                }}
                .data-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                .data-table th, .data-table td {{
                    padding: 8px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                .data-table th {{
                    background-color: #f2f2f2;
                }}
                .data-table tr:hover {{
                    background-color: #f5f5f5;
                }}
                .chart-title {{
                    text-align: center;
                    font-weight: bold;
                    margin-bottom: 10px;
                }}
                .center-text {{
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    font-size: 24px;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Your Ancestry Results</h1>
                <div class="chart-title">Ancestry Distribution</div>
                <div class="chart-container">
                    <canvas id="ancestryChart"></canvas>
                </div>
                
                <h2>Detailed Results</h2>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Ancestry</th>
                            <th>Percentage</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        # Add table rows
        for label, value in sorted_data.items():
            percentage = float(value) * 100
            html += f"""
                        <tr>
                            <td>{format_ancestry_name(label)}</td>
                            <td>{percentage:.2f}%</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
            </div>
            
            <script>
                const formatLabels = (labels) => {
                    return labels.map(label => {
                        return label.split('_').map(word => 
                            word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
                        ).join(' ');
                    });
                };
                const ctx = document.getElementById('ancestryChart').getContext('2d');
                const ancestryChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: formatLabels(""" + str(labels) + """),
                        datasets: [{
                            data: """ + str(values) + """,
                            backgroundColor: """ + str(colors) + """,
                            borderColor: 'white',
                            borderWidth: 1,
                            hoverOffset: 15
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '40%',  
                        plugins: {
                            legend: {
                                position: 'right',
                                labels: {
                                    padding: 20,
                                    boxWidth: 15,
                                    font: {
                                        size: 12
                                    }
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const label = context.label || '';
                                        const value = context.raw || 0;
                                        return `${label}: ${value.toFixed(2)}%`;
                                    }
                                }
                            }
                        },
                        animation: {
                            animateScale: true,
                            animateRotate: true
                        }
                    }
                });
                
                const total = """ + str(values) + """.reduce((acc, val) => acc + val, 0).toFixed(2);
                
                if (!Chart.registry.getPlugin('centerTextPlugin')) {
                    const centerTextPlugin = {
                        id: 'centerTextPlugin',
                        afterDraw: function(chart) {
                            const width = chart.width;
                            const height = chart.height;
                            const ctx = chart.ctx;
                            
                            ctx.restore();
                            ctx.font = '16px Arial';
                            ctx.textBaseline = 'middle';
                            ctx.textAlign = 'center';
                            
                            ctx.fillText('Total', width / 2, height / 2 - 15);
                            ctx.font = 'bold 24px Arial';
                            ctx.fillText(total + '%', width / 2, height / 2 + 10);
                            
                            ctx.save();
                        }
                    };
                    Chart.register(centerTextPlugin);
                }
            </script>
        </body>
        </html>
        """
        
        return html
    except Exception as e:
        # In case of error, return a simple error page
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error Processing Ancestry Data</title>
        </head>
        <body>
            <h1>Error Processing Ancestry Data</h1>
            <p>There was an error generating the ancestry visualization: {str(e)}</p>
            <pre>{json.dumps(data, indent=2)}</pre>
        </body>
        </html>
        """

def format_ancestry_name(name):
    """
    Formats the ancestry name for better display.
    Example: "AFR_NORTE" becomes "African North"
    """
    replacements = {
        "AFR": "African",
        "EUR": "European",
        "ASIA": "Asian",
        "ESTE": "East",
        "NORTE": "North",
        "OESTE": "West",
        "SUR": "South",
        "SURESTE": "Southeast",
        "NORESTE": "Northeast",
        "SUROESTE": "Southwest",
        "MEDIO_ORIENTE": "Middle East",
        "JUDIO": "Jewish",
        "AMAZONAS": "Amazonian",
        "ANDES": "Andean",
        "OCEANIA": "Oceanic",
        "NAHUA_OTOMI": "Nahua-Otomi"
    }
    
    parts = name.split('_')
    formatted_parts = []
    
    for part in parts:
        if part in replacements:
            formatted_parts.append(replacements[part])
        else:
            # Capitalize the first letter of words not in the replacements dictionary
            formatted_parts.append(part.capitalize())
    
    return " ".join(formatted_parts)




@mcp.tool()
async def mint_my_ancestry_results() -> str:
    """
    Gets the ancestry results for a user.
    If no signature exists, it requests one through the signature server.
    
    return: Allways return the result in an HTML artifact preview
    the ip asseet return with the mainnnet story url: https://explorer.story.foundation/ipa/<IP_ID>

    the transaction hash return using the block explorer: https://www.storyscan.io/tx/<TX_HASH>
    """
    global user_signature
    if not user_signature:
        server_result = await start_signature_server()
        progress_message = f"Iniciando proceso de firma...\n{server_result}\n\nPor favor, completa el proceso de firma en la página web..."
        max_attempts = 60
        attempt = 0
        while not user_signature and attempt < max_attempts:
            await asyncio.sleep(2)
            attempt += 1
            
        if not user_signature:
            return "Tiempo de espera agotado. No se recibió ninguna firma. Por favor, intente de nuevo."
    try:
        url = f"{GENBANK_API_BASE}/api_somos_dao/min_ancestry_ip_asset"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, 
                params={"user_singature": user_signature},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return data
    except Exception as e:
        return f"Error al procesar la solicitud: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")