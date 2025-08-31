export default {
  async fetch(request, env, ctx) {
    // Handle CORS preflight requests
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, HEAD, POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type',
        }
      });
    }

    try {
      // Get the URL parameter from the request
      const url = new URL(request.url);
      const teraboxUrl = url.searchParams.get('url');
      
      // Check if URL parameter is provided
      if (!teraboxUrl) {
        return new Response('Please provide a Terabox URL using ?url= parameter', {
          status: 400,
          headers: { 
            'Content-Type': 'text/plain',
            'Access-Control-Allow-Origin': '*'
          }
        });
      }
      
      // Construct the original API URL
      const apiUrl = `https://terabox.bdbots.xyz/dl?url=${encodeURIComponent(teraboxUrl)}`;
      
      // Fetch data from the original API with timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
      
      const response = await fetch(apiUrl, {
        signal: controller.signal,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
      });
      
      clearTimeout(timeoutId);
      
      // Check if the API response is successful
      if (!response.ok) {
        return new Response('Failed to fetch data from Terabox API', {
          status: response.status,
          headers: { 
            'Content-Type': 'text/plain',
            'Access-Control-Allow-Origin': '*'
          }
        });
      }
      
      // Parse the JSON response
      const data = await response.json();
      
      // Check if files array exists and has at least one file
      if (!data.files || data.files.length === 0) {
        return new Response('No files found in the response', {
          status: 404,
          headers: { 
            'Content-Type': 'text/plain',
            'Access-Control-Allow-Origin': '*'
          }
        });
      }
      
      // Get the first file's direct download link
      const directLink = data.files[0].direct_link;
      
      // Check if direct link exists
      if (!directLink) {
        return new Response('No direct download link found', {
          status: 404,
          headers: { 
            'Content-Type': 'text/plain',
            'Access-Control-Allow-Origin': '*'
          }
        });
      }

      // Option 1: Direct redirect (simple)
      // return Response.redirect(directLink, 302);

      // Option 2: Proxy the download (better for CORS and reliability)
      return await handleProxyDownload(directLink, request);
      
    } catch (error) {
      // Handle any errors
      return new Response(error.name === 'AbortError' ? 'Request timeout' : `Error: ${error.message}`, {
        status: 500,
        headers: { 
          'Content-Type': 'text/plain',
          'Access-Control-Allow-Origin': '*'
        }
      });
    }
  }
};

// Proxy function to handle the download
async function handleProxyDownload(downloadUrl, originalRequest) {
  try {
    // Fetch the file from the direct link
    const fileResponse = await fetch(downloadUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://www.terabox.com/'
      }
    });

    if (!fileResponse.ok) {
      throw new Error(`Download failed with status: ${fileResponse.status}`);
    }

    // Get response headers
    const headers = new Headers(fileResponse.headers);
    
    // Set CORS headers
    headers.set('Access-Control-Allow-Origin', '*');
    headers.set('Access-Control-Expose-Headers', '*');
    
    // Remove problematic headers
    headers.delete('content-security-policy');
    headers.delete('x-frame-options');
    headers.delete('x-content-type-options');

    // Create a new response with the file data and modified headers
    return new Response(fileResponse.body, {
      status: fileResponse.status,
      statusText: fileResponse.statusText,
      headers: headers
    });

  } catch (error) {
    // If proxy fails, fall back to redirect
    return Response.redirect(downloadUrl, 302);
  }
}

// Alternative: Simple redirect version (uncomment if you prefer just redirects)
/*
export default {
  async fetch(request, env, ctx) {
    // Add CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, HEAD, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      const url = new URL(request.url);
      const teraboxUrl = url.searchParams.get('url');
      
      if (!teraboxUrl) {
        return new Response('Please provide a Terabox URL using ?url= parameter', {
          status: 400,
          headers: { ...corsHeaders, 'Content-Type': 'text/plain' }
        });
      }
      
      const apiUrl = `https://terabox.bdbots.xyz/dl?url=${encodeURIComponent(teraboxUrl)}`;
      const response = await fetch(apiUrl);
      
      if (!response.ok) {
        return new Response('Failed to fetch data from Terabox API', {
          status: response.status,
          headers: { ...corsHeaders, 'Content-Type': 'text/plain' }
        });
      }
      
      const data = await response.json();
      
      if (!data.files || data.files.length === 0 || !data.files[0].direct_link) {
        return new Response('No download link found', {
          status: 404,
          headers: { ...corsHeaders, 'Content-Type': 'text/plain' }
        });
      }
      
      const directLink = data.files[0].direct_link;
      return Response.redirect(directLink, 302);
      
    } catch (error) {
      return new Response(`Error: ${error.message}`, {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'text/plain' }
      });
    }
  }
};
*/
