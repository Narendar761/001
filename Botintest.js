export default {
  async fetch(request, env, ctx) {
    try {
      // Get the URL parameter from the request
      const url = new URL(request.url);
      const teraboxUrl = url.searchParams.get('url');
      
      // Check if URL parameter is provided
      if (!teraboxUrl) {
        return new Response('Please provide a Terabox URL using ?url= parameter', {
          status: 400,
          headers: { 'Content-Type': 'text/plain' }
        });
      }
      
      // Construct the original API URL
      const apiUrl = `https://terabox.bdbots.xyz/dl?url=${encodeURIComponent(teraboxUrl)}`;
      
      // Fetch data from the original API
      const response = await fetch(apiUrl);
      
      // Check if the API response is successful
      if (!response.ok) {
        return new Response('Failed to fetch data from Terabox API', {
          status: response.status,
          headers: { 'Content-Type': 'text/plain' }
        });
      }
      
      // Parse the JSON response
      const data = await response.json();
      
      // Check if files array exists and has at least one file
      if (!data.files || data.files.length === 0) {
        return new Response('No files found in the response', {
          status: 404,
          headers: { 'Content-Type': 'text/plain' }
        });
      }
      
      // Get the first file's direct download link
      const directLink = data.files[0].direct_link;
      
      // Check if direct link exists
      if (!directLink) {
        return new Response('No direct download link found', {
          status: 404,
          headers: { 'Content-Type': 'text/plain' }
        });
      }
      
      // Redirect directly to the download link
      return Response.redirect(directLink, 302);
      
    } catch (error) {
      // Handle any errors
      return new Response(`Error: ${error.message}`, {
        status: 500,
        headers: { 'Content-Type': 'text/plain' }
      });
    }
  }
};
