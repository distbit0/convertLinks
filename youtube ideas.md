
Implementation detail
Get the audio transcript. I get it directly from the youtube transcript. If you want you can whisper the audio to get more clear transcript.

Combine the transcript between the 30 seconds interval. Now we have texts like this

{
  'text': "...",
  'start': '00:00:00',
  'end': '00:00:31',
  'duration': '00:00:31'}
Take screenshot from the video using opencv at the start for every element in our transcript. Save the screenshot with names in {seconds}.jpeg. for example, the first image will be saved as 0.jpeg and second image will be stored as 31.jpeg and so on.

Combine text and image between 2 minutes interval and keep previous context in the prev_sentence.

An example element will be like this:

{'combined_text': "...",
  'prev_sentence': '...',
  'images': ['/Users/cohlem/Desktop/screenshots/7985.jpeg',
   '/Users/cohlem/Desktop/screenshots/0.jpeg',
   '/Users/cohlem/Desktop/screenshots/31.jpeg',
   '/Users/cohlem/Desktop/screenshots/63.jpeg'],
  'start': '00:00:00',
  'end': '00:02:06'}
Now send each of the combined text + images that we get from step 4. to GPT-4V with a prompt to generate content. This process can be run parallelly which will reduce generation time.

 
1. Get youtube transcript
from youtube_transcript_api import YouTubeTranscriptApi
    
video_id = "zduSFxRajkE"

transcript = YouTubeTranscriptApi.get_transcript(video_id)
2. Combine transcript between 30 seconds interval
from datetime import datetime, timedelta

def format_time(seconds):
    # Convert seconds to timedelta object
    delta = timedelta(seconds=seconds)
    # Extract hours, minutes, and seconds
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    # Format the time as HH:MM:SS
    formatted_time = '{:02}:{:02}:{:02}'.format(hours, minutes, seconds)
    return formatted_time

def combine_transcript(transcript):
    combined_transcript = []
    current_interval_start = transcript[0]['start']
    current_interval_text = ""

    for item in transcript:
        if item['start'] - current_interval_start > 30:  # Check if 5 minutes have passed
            duration = item['start'] - current_interval_start
            combined_transcript.append({
                'text': current_interval_text.strip(),
                'start': format_time(current_interval_start),
                'end': format_time(current_interval_start + duration),
                'duration': format_time(duration)
            })
            current_interval_start = item['start']
            current_interval_text = ""

        current_interval_text += item['text'] + " "

    # Append the remaining text as the last interval
    duration = transcript[-1]['start'] - current_interval_start
    combined_transcript.append({
        'text': current_interval_text.strip(),
        'start': format_time(current_interval_start),
        'end': format_time(current_interval_start + duration),
        'duration': format_time(duration)
    })

    return combined_transcript

# The combined object is stored as loaded_object
loaded_object = combine_transcript(transcript)
3. Take screenshots using opencv
import cv2

def take_screenshot(video_path, output_path, timestamp):
    """
    This function takes a video file, a list of timestamps, and an output directory path as input.
    It reads the video file frame by frame, extracts frames at the specified timestamps, and saves them as JPEG images.
    If the video file cannot be opened or if there is an error reading frames at the specified timestamps, appropriate error messages are printed.
    Once all frames are extracted, the function releases the video capture object.
    """
    # Open the video file
    cap = cv2.VideoCapture(video_path)
    
    # Check if the video opened successfully
    if not cap.isOpened():
        print("Error: Couldn't open the video file.")
        return
    
    for item in timestamp:
    
        # Set the timestamp (in milliseconds)
        cap.set(cv2.CAP_PROP_POS_MSEC, item * 1000)

        # Read the frame at the specified timestamp
        success, frame = cap.read()

        # Check if frame reading was successful
        if not success:
            print("Error: Couldn't read frame at the specified timestamp.")
            return

        # Write the frame to an image file
        cv2.imwrite(output_path + f"{item}.jpeg", frame)
    
    # Release the video capture object
    cap.release()
convert time to seconds
For example:

convert 00:00:30 to 30 seconds and so on.

def timestamp_to_seconds(timestamp):
    # Split the timestamp into hours, minutes, and seconds
    hours, minutes, seconds = map(int, timestamp.split(':'))
    
    # Calculate the total seconds
    total_seconds = hours * 3600 + minutes * 60 + seconds
    
    return total_seconds
Take screenshot at the beginning
Since, our transcribed text is in the interval of 30 seconds, we take screenshots at the start.

For example:

The first text is like this

{'text': "hi everyone so in this video I'd like us to cover the process of tokenization in large language models now you see here that I have a set face and that's because uh tokenization is my least favorite part of working with large language models but unfortunately it is necessary to understand in some detail because it it is fairly hairy gnarly and there's a lot of hidden foot guns to be aware of and a lot of oddness with large language models typically traces back to tokenization so what is tokenization now in my previous video Let's Build GPT from scratch uh we",
  'start': '00:00:00',
  'end': '00:00:31',
  'duration': '00:00:31'
  }
We take a screenshot at start i.e '00:00:00' i.e 0 seconds. We do the same for every text in the loaded_object

video_path = '/Users/cohlem/Downloads/tutorial.mp4'
output_path = f'/Users/cohlem/Desktop/screenshots/'
timestamp_in_seconds = [timestamp_to_seconds(time['start']) for time in loaded_object]


take_screenshot(video_path, output_path,timestamp_in_seconds )
Function to compare how similar two images are
The reason for comparing two images is to minimize the number of images that are passed to the GPT-4V model. Later on you'll see we'll pass 4 images in one pass. So our goal is to minimize the number of images that we pass to the GPT-4V model in one pass.

We compare these two images by comparing their MSE( MEAN SQUARED ERROR). In simpler terms, the MSE measures the average squared difference between the pixel values of the two images. A lower MSE indicates that the two images are more similar, while a higher MSE indicates greater dissimilarity.

The threshold I've set to differentiate an image from another image is set to 10. This value was set manually by looking at two images and their MSE, I found images below 10 were pretty similar.

import cv2
import numpy as np


def compare_images(img1, img2, method="mse"):
    """
    Compares the similarity or difference between two images using # Mean Squared Error (MSE) methods.

    Args:
      img1: First image as a NumPy array.
      img2: Second image as a NumPy array.
      method: Method to use for comparison. Options include "mse"

    Returns:
      A value representing the similarity or difference based on the chosen method. Less the values more similar they are
    """

    # Ensure images are grayscale and have the same dimensions
    img1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY) if len(img1.shape) > 2 else img1
    img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY) if len(img2.shape) > 2 else img2
    img1 = (
        cv2.resize(img1, (img2.shape[1], img2.shape[0]))
        if img1.shape != img2.shape
        else img1
    )
    img2 = (
        cv2.resize(img2, (img1.shape[1], img1.shape[0]))
        if img2.shape != img1.shape
        else img2
    )

    if method == "mse":
        # Mean Squared Error (MSE)
        diff = np.square(img1 - img2).mean()
        return diff

    else:
        raise ValueError(f"Invalid comparison method: {method}")


# Example usage
img1 = cv2.imread("/Users/cohlem/Desktop/screenshots/967.jpeg")
img2 = cv2.imread("/Users/cohlem/Desktop/screenshots/999.jpeg")

mse = compare_images(img1, img2, method="mse")


print(f"MSE: {mse}")
MSE: 34.96286024305556
 
4. Combining the transcript and images within 2 minute interval.
Making something out of 30 second transcript would not yeild a proper readable content. For that, we will now combine all the text and the images between every 2 minute interval. As you can see we also have another key called prev_sentence in the dictionary below. This is because most of the combined context will have cut off text, to keep some context from previous part we add prev_setence which is the previous 30 second transcript.

for example. Let's say each of these numbers represent a 30 second transcript.

transcript = [0 1 2 3 4 5 6 7 8]

the combined text will now have texts from

i. [0 1 2 3] and it will have prev_sentence= '' (because no context before 0)

ii. [4,5,6,7] and it will have prev_sentence = [0]

A sample element in the final_list would look like this

{'combined_text': "...",
  'prev_sentence': "...",
  'images': ['/Users/cohlem/Desktop/screenshots/126.jpeg',
   '/Users/cohlem/Desktop/screenshots/156.jpeg',
   '/Users/cohlem/Desktop/screenshots/187.jpeg',
   '/Users/cohlem/Desktop/screenshots/217.jpeg'],
  'start': '00:02:06',
  'end': '00:04:08'},
n = 4 # Represents 2 minute range
final_list = []

cnt = 0
for i in range(0, len(loaded_object), n):
    
    combined_text = ''
    images = []
    prev = loaded_object[i-1]['text'] if i>0 else ""
    start = loaded_object[i]['start']
    end = ''
    
    for j in range(n):
        if i + j < len(loaded_object):
            combined_text += " " + loaded_object[i + j]['text']
            end = loaded_object[i + j]['end']
            
#             print(i+j-1, i+j)
            
            prev_image_path = f"/Users/cohlem/Desktop/screenshots/{timestamp_to_seconds(loaded_object[i + j - 1]['start'])}.jpeg"
            curr_image_path = f"/Users/cohlem/Desktop/screenshots/{timestamp_to_seconds(loaded_object[i + j]['start'])}.jpeg"
            
            prev_image = cv2.imread(prev_image_path)
            curr_image = cv2.imread(curr_image_path)

            if compare_images(prev_image, curr_image) >= 10:
                images.append(curr_image_path) 
    #             print(prev_image)
                cnt +=1

    
    final_list.append({'combined_text' : combined_text, 'prev_sentence' : prev, 'images' : images, 'start': start, 'end': end})
 
5. Now send each of the combined text + images that we get from step 4. to GPT-4V with a prompt to generate content.
from IPython.display import display, Image, Audio

import cv2  # We're using OpenCV to read video, to install !pip install opencv-python
import base64
import time
from openai import OpenAI
# Function to encode the image while passing it to GPT-4V
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
Enter OpenAI Key
from getpass import getpass

api_key = getpass('Enter your key')
Enter your key········
Function to make OpenAI request.
client = OpenAI(api_key=api_key)

def generate_answer(prompt):
    
    params = {
        "model": "gpt-4-vision-preview",
        "messages": prompt,
        "max_tokens": 2000,
    }

    result = client.chat.completions.create(**params)
    #print(result.choices[0].message.content)
    
    return result.choices[0].message.content
Prompt generation.
The prompt below is just a sample and needs a lot of improvement to get the most detailed response.

def generate_prompt(current_text, previous_text, images):
    
    PROMPT_MESSAGES = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"""
                    
                     You will be given CURRENT TEXT of transcribed audio and the images from a youtube video.
                     Your task is to curate a section of blog which should have the exact explanation of topics which are being discussed in the image and 
                     in the CURRENT TEXT. 
                     
                     The images and the CURRENT TEXT may contain complex topic explanation. You have to break down
                     complex topics into sub topics step-by-step and explain them in detail.
                     If the CURRENT TEXT is not sufficient or cut off, you can take reference from the PREVIOUS TEXT.
                     
                     Write the blog section in first-person style.
                     
                     If codes are being explained you also need to include them in your answer.
                     If some references are being made you can add them in Blockquotes (>)
                     DO NOT include any conclusion in the output.
                     DO NOT include your opinions in the final response.
                     Apply heading level 3 (###) to the main topic and use lower-level headings such as (####) if there are any sub-topics.
                     
                     Your response should be as detailed as possible.
    
                     You should output in markdown syntax

                     PREVIOUS TEXT: {previous_text}

                     CURRENT TEXT: {current_text}
                     """},
                    *map(lambda x: {'type' : 'image_url', 'image_url' : f"data:image/jpeg;base64,{encode_image(x)}"}, images)
                ],
            }
    ]
    
    return PROMPT_MESSAGES
 
Generate blog section from each combined text + images.
I've run this process serially because of my low TPM rates (token per minute). You can run this parallelly if you have higher TPM rates.

If you need more information about token per API cll then,

each image is about 1105 tokens, each call to api contains max 4 images(could be less than 4) so 1105x4 = 4420 tokens,

combined_text + prev_sentence + prompt = approx 800 tokens

output = approx 1000 tokens.

total tokens = 4420 + 800 + 1000 = approx 6220 tokens

You can generate the answers parallelly with higher TPM.

The generation takes close to $5 in total

def generate_all_and_save():

    for index in range(0,len(final_list)):
        try:
            current_text = final_list[index]['combined_text']
            previous_text = final_list[index]['prev_sentence']
            images = final_list[index]['images']

            prompt = generate_prompt(current_text, previous_text, images)
            answer = generate_answer(prompt)

            # Set file path for output
            file_path = f"/Users/cohlem/Desktop/outputs/{index}.txt"
            
            # Open the file in write mode ('w')
            with open(file_path, 'w') as file:
                # Write the content to the file
                file.write(answer)

            print(f"Saved content for INDEX: {index}", file_path)

            # wait until  minute, If you have higher TPM rates you can parallelize this generation.
            time.sleep(60)
        except Exception as e:
            print(f'Error while processing INDEX: {index}, \n ERROR: {e}')
        
        
        
generate_all_and_save()
 
Save outputs in a README.md
with exact timestamps for each 2 minute interval

import os

# Directory containing the text files
directory = '/Users/cohlem/Desktop/outputs/'
youtube_link = "https://youtu.be/zduSFxRajkE?si=6vm4GUe1GMvz4U1W&t="
combined_content = ''
# Iterate over the indices of final_list
for index in range(len(final_list)):
    # Construct the filename based on the index
    filename = f"{index}.txt"
    file_path = os.path.join(directory, filename)

    # Check if the file exists
    if os.path.exists(file_path):
        # Open and read the file
        with open(file_path, 'r') as file:
            content = file.read()
            start_time = final_list[index]['start']
            end_time = final_list[index]['end']
            
            timestamp = f"{start_time} - {end_time} "
            
            combined_content = f"{combined_content} \n\n [{timestamp}]({youtube_link}{timestamp_to_seconds(start_time)}) \n\n {content}"
        
#             print(f"Content of {filename}: {content}")
    else:
        print(f"File {filename} does not exist.")
 
with open("Let's-build-the-GPT-Tokenizer.md", "w") as file:
    file.write(combined_content)