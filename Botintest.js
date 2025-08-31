export default {
  async fetch(request, env, ctx) {
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, HEAD, POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type',
        }
      });
    }

    const url = new URL(request.url);
    const teraboxUrl = url.searchParams.get('url');
    const proxyMode = url.searchParams.get('proxy') !== 'false'; // Default: true

    if (!teraboxUrl) {
      return new Response('Please provide a Terabox URL using ?url= parameter', {
        status: 400,
        headers: { 
          'Content-Type': 'text/plain',
          'Access-Control-Allow-Origin': '*'
        }
      });
    }

    try {
      const apiUrl = `https://terabox.bdbots.xyz/dl?url=${encodeURIComponent(teraboxUrl)}`;
      
      const response = await fetch(apiUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
          'Accept': 'application/json',
          'Referer': 'https://terabox.bdbots.xyz/'
        }
      });

      if (!response.ok) throw new Error('API request failed');

      const data = await response.json();
      const directLink = data.files?.[0]?.direct_link;

      if (!directLink) throw new Error('No direct link found');

      // Choose between redirect or proxy mode
      if (!proxyMode) {
        // Redirect mode
        return Response.redirect(directLink, 302);
      } else {
        // Proxy mode - stream the file through the worker
        const fileResponse = await fetch(directLink, {
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://terabox.com/'
          }
        });

        const headers = new Headers(fileResponse.headers);
        headers.set('Access-Control-Allow-Origin', '*');
        headers.delete('content-security-policy');
        headers.delete('x-frame-options');

        return new Response(fileResponse.body, {
          status: fileResponse.status,
          headers: headers
        });
      }

    } catch (error) {
      return new Response(`Error: ${error.message}`, {
        status: 500,
        headers: { 
          'Content-Type': 'text/plain',
          'Access-Control-Allow-Origin': '*'
        }
      });
    }
  }
};
