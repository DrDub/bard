#!/usr/bin/env python
# generate random text using trigrams and markov chains
# supports plain text and part-of-speech tagged text.
import re
import sys
import random
import nltk
import cPickle as pickle

def detokenize(tokens):
    '''
    A humble attempt at converting a list of tokens into text.

    Pass a list of tokens, and you will receive a string formatted
    like a novel. Dialogue is placed on its own line.

        >>> tokens = ['``', 'What', '...', 'is', 'the', 'airspeed', 'velocity', 'of', 'an', 'unladen', 'swallow', '?', "''", \
                      '``', 'African', 'or', 'European', '?', "''", \
                      '``', 'I', 'do', "n't", "know", "that", '!', "''"]
        >>> sentence = detokenize(tokens)
        >>> print sentence
        ``What... is the airspeed velocity of an unladen swallow?''
        <BLANKLINE>
        ``African or European?''
        <BLANKLINE>
        ``I don't know that!''

        >>> tokens = ['``', 'It', 'is', 'but', 'a', 'scratch', '.', "''", \
                      '``', 'No', 'it', "'s", "not", '!', "Your", "arm", "'s", "off", "!", "''"]
        >>> sentence = detokenize(tokens)
        >>> print sentence
        ``It is but a scratch.''
        <BLANKLINE>
        ``No it's not! Your arm's off!''

    '''
    #print >> sys.stderr, "detokenizing tokens..."

    output = ''
    for i, token in enumerate(tokens):
        # next token; previous token
        try:
            next_token = tokens[i+1]
        except IndexError:
            next_token = ''
        if i != 0:
            prev_token = tokens[i-1]
        else:
            prev_token = ''

        # skip double punctuation.
        if token == next_token and token in "!.?;":
            continue

        # add the token to the output.
        output += token

        # add spacing.
        if next_token in '...!?.,\'\')";:' or token in '(``':
            # punctuation does not require spacing
            output += ''
        elif re.search("\'\w+", next_token):
            # don't put space in the middle of contractions
            output += ''
        elif ((token in "!?." and prev_token == "''") or 
              (token in "!?." and next_token == "``") or
              (token in "''" and prev_token in "!?.")):
            # this is dialogue, put it on its own line
            output += '\n\n'
        else:
            # normal text; just add a space
            output += ' '

    return output
 

class MarkovTextGenerator:
    '''
    Uses a Markov chain to generate random text from a list of tokens.

    The tokens can be POS-tagged (a list of tuples) or not (a list of strings).

    '''

    def __init__(self, tokens, use_cache=False):
        '''
        Initializes the MarkovTextGenerator.

        If use_cache is True, the MarkovTextGenerator will attempt to
        use a pickled version of the trigram index. This provides a performance
        benefit on large corpora (such as the entire Brown corpus) but is slightly
        slower with smaller corpora (such as the science fiction category of the Brown
        corpus).
        '''

        self.tokens = tokens
        self.trigrams = nltk.util.trigrams(self.tokens)
        self.cache = self._generate_cache(self.trigrams, use_cache)
        self.tagged = self.istagged()

    def _generate_cache(self, trigrams, use_cache):
        ''' generate a trigram index from a list of trigrams
        
        where keys are (v1, v2) and value is list of possible v3's '''
        try:
            if use_cache:
                #print >> sys.stderr, "loading trigram cache..."
                cachefile = open('.trigram_cache', 'rb')
                cache = pickle.load(cachefile)
                cachefile.close()
            else:
                raise Exception('Not using cache...')
        except:
            #print >> sys.stderr, "generating trigram cache..."
            cache = {}
            for w1, w2, w3 in trigrams:
                key = (w1, w2)
                if key in cache:
                    cache[key].append(w3)
                else:
                    cache[key] = [w3]
            if use_cache:
                cachefile = open('.trigram_cache', 'wb')
                pickle.dump(cache, cachefile, -1)
                cachefile.close()
        return cache
        
    def pseudorandom_text(self, w1=None, w2=None, length=100):
        ''' 
        uses a Markov chain to produce pseudorandom text.

        w1 -> starting word
        w2 -> second word
        length -> try to produce this many tokens

        Contains some rules to ensure that the resultant text is logical,
        such as trying to close quotations and parentheses and not inserting
        quotations where they don't make sense. However, this is not always
        possible and thus there will still be some misplaced quotation
        marks and parentheses. Furthermore, this function will not stop producing
        text until it is satisfied that parentheses and quotations have been closed
        and the last character marks the end of a sentence.

            >>> tokens = nltk.corpus.brown.tagged_words(categories='fiction')
            >>> m = MarkovTextGenerator(tokens)
            >>> text = m.pseudorandom_text(length=100)
            >>> isinstance(text, str)
            True

        '''
        #print >> sys.stderr, "generating pseudorandom text..."
        if w1 is None and w2 is None:
            w1, w2 = self.get_starter()

        results = []
        search_for = []
        exclude = ["''", ')']
        finished = False
        while not finished:
            # append the current token to the results.
            if self.tagged:
                current_tag = w1[1]
                results.append(w1[0])
                if len(results) >= length and not search_for and '.!?' in w1[0]:
                    finished = True
            else:
                current_tag = w1
                results.append(w1)
                if len(results) >= length and not search_for and '.!?' in w1:
                    finished = True

            # if something has been opened, try to close it.
            if current_tag == '(':
                search_for.append(')')
            elif current_tag == "``":
                search_for.append("''")

            # find the next token (but don't open anything if something is already open)
            # we search for the token which will close the latest item opened.
            try:
                need = search_for[-1]
            except IndexError:
                need = None
            try:
                w1, w2 = self.get_next(w1, w2, need, exclude=exclude)
                if need:
                    search_for.pop()
            except:
                try:
                    try:
                        w1, w2 = self.get_next(w1, w2, None, exclude=exclude)
                    except Exception as e:
                        w1, w2 = self.get_next(w1, w2, None)
                        #print >> sys.stderr, "forced to append something which I wanted to exclude:", w2
                except Exception as e:
                    print >> sys.stderr, e
                    return detokenize(results) + "."
    
        return detokenize(results)

    def markov_text(self, w1=None, w2=None, length=100):
        ''' 
        A pure version of the pseudorandom Markov chain text generator 
        
        w1 -> starting word
        w2 -> second word
        length -> number of tokens to produce

        This version does not have any additional intelligence, so it will produce
        illogical sentences. However, it will always produce the correct length.

            >>> tokens = nltk.corpus.brown.tagged_words(categories="fiction")
            >>> m = MarkovTextGenerator(tokens)
            >>> text = m.markov_text(length=100)
            >>> isinstance(text, str)
            True

        '''
        if w1 is None and w2 is None:
            w1, w2 = self.get_starter()

        results = []
        for i in range(length):
            if self.tagged:
                results.append(w1[0])
            else:
                results.append(w1)

            w1, w2 = w2, random.choice(self.cache[(w1, w2)])
    
        return detokenize(results)

    def get_next(self, w1, w2, search_for, exclude=[]):
        ''' find a trigram of the form (w1, w2, search_for) '''
        results= []
        if self.tagged:
            for possibility in self.cache[(w1, w2)]:
                if search_for:
                    if possibility[1] == search_for:
                        results.append(possibility)
                else:
                    if possibility[0] not in exclude:
                        results.append(possibility)
        else:
            for possibility in self.cache[(w1, w2)]:
                if search_for:
                    if possibility == search_for:
                        results.append(possibility)
                else:
                    if possibility not in exclude:
                        results.append(possibility)

        #print "searching for:"+str(search_for), "w1="+str(w1), "w2="+str(w2), "results="+str(results)
        return w2, random.choice(results)
   
    def get_largest(self):
        ''' return the key of the item in the cache with the most possibilities '''
        most = 0
        largest = None
        for (key, possibilities) in self.cache.items():
            if len(possibilities) > most:
                most = len(possibilities)
                largest = key
        return largest

    def get_starter(self):
        ''' return the key of the item in the cache which is best suited for starting the text. '''
        most = 0
        best = None
        if self.istagged():
            for (key, possibilities) in self.cache.items():
                if key[0][0].istitle():
                    if len(possibilities) > most:
                        most = len(possibilities)
                        best = key
        else:
            for (key, possibilities) in self.cache.items():
                if key[0].istitle():
                    if len(possibilities) > most:
                        most = len(possibilities)
                        best = key
        return best

    def istagged(self):
        ''' determine whether our tokens are part-of-speech tagged or not '''
        try:
            if isinstance(self.get_largest()[0], tuple):
                return True
            else:
                return False
        except:
            return False

    def get_tags(self):
        ''' return the different part-of-speech tags in the cache'''
        tags = []
        if self.istagged():
            for possibilities in self.cache.values():
                for possibility in possibilities:
                    tags.append(possibility[1])
            return sorted(set(tags))
        return False

if __name__ == "__main__":
    import doctest
    doctest.testmod()
