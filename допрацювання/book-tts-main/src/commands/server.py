from http.server import HTTPServer, BaseHTTPRequestHandler

FILE_PATH = './output/test/result.wav'

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>Welcome to the Audio Server</h1></body></html>')

        # try:
        #     with open(FILE_PATH, 'rb') as f:
        #         content = f.read()

        #     self.send_response(200)
        #     self.send_header('Content-type', 'audio/wav')
        #     self.send_header('Content-Length', str(len(content)))
        #     self.end_headers()
        #     self.wfile.write(content)
        # except FileNotFoundError:
        #     self.send_response(404)
        #     self.end_headers()
        #     self.wfile.write(b'File not found')

class ServerCommand:
    def run(self):
        httpd = HTTPServer(('0.0.0.0', 8090), SimpleHandler)
        print("Serving on port 8090...")
        httpd.serve_forever()