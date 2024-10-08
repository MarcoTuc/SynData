from typing import Callable
import random
import math 
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from datasets import load_dataset
from templates import templates


# gpt2 to evaluate cross-entropy and train
device = torch.device("cuda:1")

model_name = "gpt2-xl"
model = AutoModelForCausalLM.from_pretrained(model_name).to(device)
tokenizer = AutoTokenizer.from_pretrained(model_name, clean_up_tokenization_spaces=True)
tokenizer.pad_token = tokenizer.eos_token
model.config.pad_token_id = model.config.eos_token_id

# contex window size of the model used to define how big training data should be
ctx_window = model.config.max_position_embeddings

# we'll use 2/3 of the context window to put the text to process and the other third to put the result of the task
sub_window_size = math.floor(ctx_window/3)

def tokenize(text): return tokenizer(text, return_tensors="pt", padding=True).to(device)
def detokenize_0(tokens): return tokenizer.decode(tokens[0], skip_special_tokens=True)
def detokenize_w(tokens): return tokenizer.decode(tokens, skip_special_tokens=True)
def detokenize_l(tokens): return [tokenizer.decode(tok, skip_special_tokens=True) for tok in tokens]

def redblue(y: tuple, red, blue):
    o = y[0]
    c = y[1]
    return f"@#@#@xent_redblue~(~[{o}><{c}]~><{red}><{blue})~:>:>:"

class XentLang:
    
    xdef = "@##$$##@"
    pot = "(("
    pct = "))"
    poq = "[["
    pcq = "]]"
    comma  = "><"
    xreturn = ">:ç%ç>:"

    mapper = {
        "(": pot,
        ")": pct,
        "[": poq,
        "]": pcq,
        ",": comma,
        ":": xreturn,
        "def": xdef,
        " ": ""
    }

    def map(self, function: str):
        for s in self.mapper.items():
            function = function.replace(*s)
        return function
    
    def invmap(self, text: str):
        mapper  = {v: k for k, v in self.mapper.items()}
        mapper.pop("")
        for s in mapper.items():
            text = text.replace(*s)
        return text

    def redblue(self, y: tuple, red, blue):
        return self.map(f"def red-blue([{y[0]}, {y[1]}], {red}, {blue}):")


database = load_dataset("wikipedia", "20220301.en", trust_remote_code=True)["train"]
num_articles = len(database)

class WikiArticle:

    def __init__(self, tokenize: Callable = tokenize):
        self.article = self.get_random_article()
        self.title = self.article["title"]
        self.slices = self.slice()
        self.tlices = self.tokenization(tokenize)

    def get_random_article(self):
        return database[random.randint(0, num_articles-1)]

    def slice(self):
        return self.article["text"].split("\n\n")

    def tokenization(self, tokenize: Callable=tokenize):
        return [tokenize(s).input_ids for s in self.slices]

    def get_training_sample(self, max_len):
        W = torch.tensor([[]]).to(device)
        for t in self.tlices[random.randint(0, len(self.tlices)-1):]:
            if W.size(1) + t.size(1) < max_len:
                W = torch.cat([W, t], dim=-1)
            else:
                break
        return W.to(torch.long)
    

class HilightWiki:

    def __init__(self, tokenize: Callable=tokenize):

        self.tokenize = tokenize
        self.model = model
        # define how you are going to separate W1 and W2
        separation = "\n"
        self.acapo = self.tokenize(separation).input_ids

        self.xentask = None
        self.textok = None

    def create(self, window_size=sub_window_size, min_len=None):
        textok, t1, t2 = self.extract(window_size, min_len)
        min_y_window = int(sub_window_size)
        i = random.randint(0, textok.size(-1) - min_y_window)
        y = textok[0][i:i+min_y_window]
        hilisorted = self.xent_sort(y.unsqueeze(0), t1, t2)

    def extract(self, window_size=sub_window_size, min_len=None):

        if min_len == None: min_len = int(window_size / 2)
        
        len1 = 0
        while len1 < min_len:
            A1 = WikiArticle(self.tokenize)
            sample1 = A1.get_training_sample(window_size)
            question1 = random.choice(templates).format(A1.title)
            title1 = self.tokenize(question1).input_ids
            len1 = sample1.size(-1)
        len2 = 0
        while len2 < min_len:
            A2 = WikiArticle(self.tokenize)
            sample2 = A2.get_training_sample(window_size)
            question2 = random.choice(templates).format(A2.title)
            title2 = self.tokenize(question2).input_ids
            len2 = sample2.size(-1)

        textok = torch.cat([sample1, self.acapo, sample2], dim=-1)

        return textok, title1, title2
    
    def xent_sort(self, y, red, blue):
        red = phrasize(red)
        red_tokens = torch.cat([red, y], dim=-1)
        red_len = red.size(-1)
        red_logits = self.model(red_tokens).logits
        red_xents  = F.cross_entropy(red_logits[0, red_len-1:][:-1], red_tokens[0, red_len-1:][1:], reduction="none")

        blue = phrasize(blue)
        blue_tokens = torch.cat([blue, y], dim=-1)
        blue_len = blue.size(-1)
        blue_logits = self.model(blue_tokens).logits
        blue_xents  = F.cross_entropy(blue_logits[0, blue_len-1:][:-1], blue_tokens[0, blue_len-1:][1:], reduction="none")

        xent_differential = red_xents - blue_xents
        _, sorting = torch.sort(xent_differential)

        return y[0, sorting]
    
    def textify_task(self):
        pass 

def phrasize(title):
    return tokenize(random.choice(templates).format(detokenize_0(title))).input_ids