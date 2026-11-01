import numpy as np

def normalized_codepoints(text):
 chars=[];digit=False
 for c in text:
  cp=ord(c)+32 if 'A'<=c<='Z'else ord(c)
  if 48<=cp<=57:
   if digit:continue
   cp=35;digit=True
  else:digit=False
  chars.append(cp)
 return chars

def position_features(text,bins=2048):
 assert bins==2048
 chars=normalized_codepoints(text);split=(len(chars)+1)//2;counts=np.zeros(2048,np.int32)
 # Original global1024 is unchanged,including grams crossing the midpoint.
 # Two512 channels use grams contained inside their Unicode midpoint segment.
 for at in range(len(chars)):
  h=2166136261
  for width in range(1,5):
   if at+width>len(chars):break
   h=((h^chars[at+width-1])*16777619)&0xffffffff;v=(h^(h>>16)^((width*0x9e3779b9)&0xffffffff))&0xffffffff
   counts[v&1023]+=1 if not(v&1024)else-1
   if at<split and at+width<=split:counts[1024+(v&511)]+=1 if not(v&512)else-1
   elif at>=split:counts[1536+(v&511)]+=1 if not(v&512)else-1
 return (np.clip(counts,-3,3)*8).astype(np.int8)
