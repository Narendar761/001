export default {
  async fetch(request, env, ctx) {
    // CORS headers for browser requests
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, HEAD, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    // Handle OPTIONS preflight requests
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: corsHeaders,
      });
    }

    // Get the URL parameter from the request
    const url = new URL(request.url);
    const teraboxUrl = url.searchParams.get('url');

    if (!teraboxUrl) {
      return new Response(JSON.stringify({ error: 'Missing url parameter' }), {
        status: 400,
        headers: {
          'Content-Type': 'application/json',
          ...corsHeaders,
        },
      });
    }

    try {
      // Fetch data from the original API
      const originalApiUrl = `https://terabox.bdbots.xyz/dl?url=${encodeURIComponent(teraboxUrl)}`;
      const apiResponse = await fetch(originalApiUrl);
      
      if (!apiResponse.ok) {
        throw new Error(`Original API returned status: ${apiResponse.status}`);
      }

      const data = await apiResponse.json();

      // Check if it's a file and has direct_link
      if (!data.isFolder && data.files && data.files.length > 0 && data.files[0].direct_link) {
        const directLink = data.files[0].direct_link;
        const proxyUrl = `https://terabox-url-fixer.amir470517.workers.dev/?url=${encodeURIComponent(directLink)}`;
        
        // Redirect directly to the proxied download link
        return Response.redirect(proxyUrl, 302);
      } else {
        return new Response(JSON.stringify({ error: 'No downloadable file found' }), {
          status: 404,
          headers: {
            'Content-Type': 'application/json',
            ...corsHeaders,
          },
        });
      }

    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: {
          'Content-Type': 'application/json',
          ...corsHeaders,
        },
      });
    }
  },
};
