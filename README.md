# batch-avif-resizer-local

A simple tool to batch compress given images to AVIF and downsize them to the breakpoints given.  

- Designed to maximize image quality per file for an image-centric site where both filesizes and image quality matter.
  - Will incrementally increase compression/reduce quality until the file either meets the given filesize limit or hits the lowest quality limit.
  - If the resulting output ends up larger than the source file for some reason, copies the source file directly to output instead.
  - If the input file is already well below the given filesize limits, will copy the source file directly to output to preserve quality.
- Runs on the local machine via docker - no reliance on web services or content delivery networks, no absurd paywalls.  
- Non-image files are copied directly to the output folder, allowing the tool to work on a large set of mixed assets.  

Created purely for my own use to optimize assets for a future version of my own website.  
If you want changes or find issue with anything, please fork and modify the code for your own use.  

