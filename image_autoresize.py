import os
import shutil
import argparse

from PIL import Image
import piexif


# Image extensions to handle
EXTS = ["jpg", "jpeg", "png", "avif", "webp"]
EXIF_EXTS = ["jpg", "jpeg", "webp"]

# A set of resolution ranges and absolute max filesizes (in bytes) per
IMAGE_SIZES = [
  # ((3840, 2561), 1.5 * 1000 * 1000), # 4K -> 1.5MB (Only used for very hires gallery views where load times aren't crucial)
  ((2560, 2049), 500 * 1000), # 2560 -> 500KB (Heros and backgrounds)
  ((2048, 1025), 300 * 1000), # 2048 -> 300KB (Large gallery views)
  ((1024, 0), 100 * 1000), # 1024 -> 100KB (Thumbnail-tier)
]
NO_RESIZE_MULTIPLIER = 0.4

BASE_QUALITY = 80
LOWEST_QUALITY = 50


class Resizer:
  def __new__(cls, source: str, dest: str, size: int):
    print(f"Resizer running on dest {dest} size {size}")
    # Handles calling imagick, filesize comparing, etc
    # If size is 0, doesn't resize
    
    # Return codes
    # 0 - success
    # -1 - Failed due to failed Image.open()
    # -2 - imagick returned an error
    # -3 - Target file was not generated after imagick call
    # 1 - Deprecated - Skipped due to given size being larger than source
    # 2 - Need to copy source over to destination due to source being smaller than dest or source already being small enough
    
    # Caller should never be passing a size greater than the greatest size in IMAGE_SIZES
    if size > IMAGE_SIZES[0][0][0]:
      raise Exception("Resizer was given a size larger than any setting in IMAGE_SIZES")
    
    try:        
      # Open source file
      image_source = Image.open(source)
      
    except:
      return -1
    
    # Get max dimen of image
    source_width = image_source.width
    source_height = image_source.height
    image_source.close()
    
    source_max_dimen = max(source_width, source_height)
    
    do_resize = True
    # If the source image is exactly sized to the target size, don't resize - just compress
    if size == source_max_dimen:
      do_resize = False
      
    # Get required filesize limit for current size
    size_setting_tuple_list = [ x for x in IMAGE_SIZES if x[0][0] >= size and x[0][1] <= size ]
    size_setting_tuple = size_setting_tuple_list[0] if len(size_setting_tuple_list) > 0 else IMAGE_SIZES[-1]
    
    filesize_limit = size_setting_tuple[1]
    print(f"Size limit - {filesize_limit}")
    
    
    # If the original filesize is already "aggressively small" before any resizing or compression, can copy over directly
    if os.path.getsize(source) < filesize_limit * NO_RESIZE_MULTIPLIER:
      print("Filesize is already very small - skip compression")
      return 2
    
    
    # If destination file already exists, delete beforehand
    if os.path.exists(dest):
      if os.path.isfile(dest):
        os.remove(dest)
      else:
        shutil.rmtree(dest)
    
    # Do the resize
    resize_flags = f"-resize {size}x\>" if source_width > source_height else f"-resize x{size}\>"
    full_resize_flags = f"-colorspace RGB -filter lanczos -define filter:lobes=3 {resize_flags} -colorspace sRGB"
    if not do_resize:
      full_resize_flags = ""
    
    quality = BASE_QUALITY
    
    # Attempt to resize with decreasing quality steps until size limit is met, bottoming out at 60
    while quality >= LOWEST_QUALITY:
      
      # If there's leftover files from the last attempt, remove before generation
      if os.path.exists(dest):
        os.remove(dest)
        
      # Generate file for current quality
      magick_return_value = os.system(f"magick {os.path.join(root, file)} {full_resize_flags} -define avif:speed=6 -define avif:chroma-subsampling=4:2:0 -quality {quality} -strip {dest}")
      # If return value isn't 0, sth failed
      if os.WEXITSTATUS(magick_return_value) != 0:
        print("Faulty magick exit code")
        return -2
      
      # If target file doesn't exist after imagick, sth failed
      if not os.path.exists(dest):
        print("Target file DNE")
        return -3
      
      # If filesize is too large, subtract quality and re-run
      if os.path.getsize(dest) > filesize_limit:
        quality -= 5
        print(f"Filesize needs reducing, dropping quality to {quality}")
        continue
      else:
        print("Filesize check passes")
        break
      
    # Final result comparison - copy source over directly if output ends up larger than input
    # TODO: This ignores sizes; what to do?
    # For treat the extra resolution as "free" since it's better than the best effort resize anyways
    if os.path.getsize(dest) >= os.path.getsize(source):
      # Let caller handle this
      return 2
    
    return 0
  

if __name__ == "__main__":
  
  description_cmd = """Image converter for generating web-friendly images from source.

- The structure of _SOURCE_FILES is replicated to _OUTPUT.
- For any encountered non-image file, the file is copied directly over to _OUTPUT.
- For any encountered image file that contains _orig, the file is compressed/resized as necessary to _OUTPUT.
- For any encountered image files that doesn't contain _orig, the file is skipped.

"""
  arg_parser = argparse.ArgumentParser(
    description=description_cmd, formatter_class=argparse.RawTextHelpFormatter)
  
  description_wipe = "Wipe the _OUTPUT directory before starting (fresh rebuild)."
  arg_parser.add_argument(
    "-w", "--wipe", dest="wipe", help=description_wipe, action="store_true")
  
  description_skip = "Skip any files that exist at the output."
  arg_parser.add_argument(
    "-s", "--skip-existing", dest="skip_existing", help=description_skip, action="store_true")
  
  args = arg_parser.parse_args()
  if args.wipe:
    print("Wiping _OUTPUT dir as requested")
    outdir = os.path.join("workdir", "_OUTPUT")
    if os.path.exists(outdir):
      if os.path.isdir(outdir):
        shutil.rmtree(outdir)
      else:
        os.remove(outdir)
  
  files_copied_directly = []
  files_error = []
  files_success = []
  files_skipped = []
  
  for (root, dirs, files) in os.walk(os.path.join("workdir", "_SOURCE_FILES"), topdown=True):
    for file in files:
      
      # Check if the corresponding output dir already exists
      # If not, create it
      output_root = root.replace("_SOURCE_FILES", "_OUTPUT")
      if not os.path.exists(output_root):
        os.makedirs(output_root)
      
      full_input_file_path = os.path.join(root, file)
      
      # If file is not an image, copy directly
      filename_separated_by_dot = file.split(".") # Splits at all dots, so one of the split strings should be the ext
      if filename_separated_by_dot[-1].casefold() not in EXTS:
        shutil.copy2(full_input_file_path, os.path.join(output_root, file))
        files_copied_directly.append(os.path.join(output_root, file))
        continue
      
      # Otherwise, the file is an image
      if "_orig." not in file:
        print(f"Image file {file} is not marked _orig - skipping")
        files_error.append((full_input_file_path, "Image file not marked _orig"))
        continue
      
      filename_separated = file.split("_orig.") # Yields ["filename_bit", "extension_without_dot"]
      
      # Generate all filesizes necessary        
      try:        
        image_source = Image.open(full_input_file_path)
      except:
        files_error.append((full_output_file_path, "Image.open() failed on source"))
      source_max_dimen = max(image_source.width, image_source.height)
      image_source.close()
      
      breakpoints_list = [ x[0][0] for x in IMAGE_SIZES ] # Full list of size breakpoints to check for source later
      
      # Note: IMAGE_SIZES = array of settings, IMAGE_SIZES[0] = first setting, IMAGE_SIZES[0][0] = first settings' image size tuple, IMAGE_SIZES[0][0][0] = maximum defined image size
      # If source_max_dimen exceeds the max setting (IMAGE_SIZES[0][0][0]), only generate the sizes in IMAGE_SIZES (i.e. don't generate sizes over 3840)
      # If source_max_dimen doesn't exceed the max setting, generate the file's original size to have a maxres option
      # -> If source_max_dimen is LTE the max setting (IMAGE_SIZES[0][0][0]), add source_max_dimen to generate list
      
      resize_list_for_image = [ x[0][0] for x in IMAGE_SIZES if x[0][0] <= source_max_dimen ] 
      if source_max_dimen <= IMAGE_SIZES[0][0][0]:
        resize_list_for_image.append(source_max_dimen)
      
      
      # Create each size
      for max_dimen in resize_list_for_image:
        # Generate output filename and path
        size_identifier = f"{max_dimen}"
        if max_dimen not in breakpoints_list:
          size_identifier = f"{max_dimen}_origsize"
        output_filename = f"{filename_separated[0]}_{size_identifier}.avif"
        full_output_file_path = os.path.join(output_root, output_filename)
        
        if args.skip_existing == True and os.path.exists(full_output_file_path):
          print(f"Skipping existing file {full_output_file_path}")
          files_skipped.append(full_output_file_path)
          continue
        
        resize_ret_value = Resizer(full_input_file_path, full_output_file_path, max_dimen)
        
        match resize_ret_value:
          
          # 0 - success
          case 0:
            files_success.append(full_output_file_path)
            
          # -1 - Failed due to failed Image.open()
          case -1:
            files_error.append((full_output_file_path, "Image.open() failed on source"))
          
          # -2 - imagick returned an error
          case -2:
            files_error.append((full_output_file_path, "ImageMagick reported an error during transform"))
          
          # -3 - Target file was not generated after imagick call
          case -3:
            files_error.append((full_output_file_path, "Target file was not generated after ImageMagick call"))
            
          # 1 - Deprecated - Skipped due to given size being larger than source
          case 1:
            pass
            
          # 2 - Need to copy source over to destination due to source being smaller than dest
          case 2:
            if os.path.exists(full_output_file_path):
              os.remove(full_output_file_path)
              
            # Copy file
            direct_copy_target_filename = f"_{max_dimen}_directcopy".join(file.split("_orig"))
            shutil.copy2(full_input_file_path, os.path.join(output_root, direct_copy_target_filename))
            # Remove EXIF for supported filetypes
            if filename_separated_by_dot[-1].casefold() in EXIF_EXTS:
              piexif.remove(os.path.join(output_root, direct_copy_target_filename))
            print("Copying source file to dest due to no size benefits")
            files_copied_directly.append(os.path.join(output_root, direct_copy_target_filename))
          
          # Everything else  
          case _:
            print(f"Unknown return value for file {full_input_file_path}")
            files_error.append((full_output_file_path, "Unknown return value from resize()"))
  
  print()
  print("Conversion complete")
  print()
  print("Skipped:")
  for file in files_skipped:
    print(file)
  print()
  print("Successfully generated files:")
  for file in files_success:
    print(file)
  print()
  print("Files copied directly:")
  for file in files_copied_directly:
    print(file)
  print()
  print("Errors:")
  for entry in files_error:
    print(entry)
  print()
  
  