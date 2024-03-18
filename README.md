This script is deisgned to create an EDL from a video file of a multiview. Right now it's set up for the first 5 boxes of a Blackmagic 2+8 multiview.

What's working:
- This script does a good job of logging camera changes and creating an EDL file.
- The initial timecode is taken from the multiview, so if your multiview recorder and cameras are timecode synced together, this will work great!
- The script is able to ask you to provide the multiview video file and the file names from your camera so that the EDL conforms easily.

What's not working:
- The timing of the cuts aren't frame perfect yet and seem to drift. This can easily be slipped but need to investigate why.
