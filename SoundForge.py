"""
Using Genetic Algorithms to create melodies
"""

import click
# Click is a Python package for creating beautiful command line interfaces
# in a composable way with as little code as necessary.
from datetime import datetime
# The datetime module supplies classes for manipulating dates and times.
from typing import List, Dict
# Typing defines a standard notation for Python function and variable type annotations.
from midiutil import MIDIFile
# MIDIUtil is a pure Python library that allows one to write multi-track Musical Instrument Digital Interface (MIDI)
# files from within Python programs.
from pyo import *
# pyo is a Python module containing classes for a wide variety of audio signal processing types.


# A genetic algorithm is a search heuristic that is inspired by Charles Darwin’s theory of natural evolution.
# This algorithm reflects the process of natural selection where the fittest individuals are selected for reproduction
# in order to produce offspring of the next generation.

# This is another program named "genetic.py" from where we are importing functions that we made to use in this program.
from Backbone import generate_genome, Genome, selection_pair, single_point_crossover, mutation

# The default number of bits per note.
BITS_PER_NOTE = 4
# The keys in which the melody can be made.
KEYS = ["C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B"]
# The scales in the melody can be made.
SCALES = ["major", "minorM", "dorian", "lydian", "majorBlues", "minorBlues"]


# Takes integers and stores it so that it con be used in the "genome_to_melody" function
def int_from_bits(bits: List[int]) -> int:
    return int(sum([bit * pow(2, index) for index, bit in enumerate(bits)]))


# This function converts the genome to a melody.
def genome_to_melody(genome: Genome, num_bars: int, num_notes: int, num_steps: int,
                     pauses: int, key: str, scale: str, root: int) -> Dict[str, list]:
    notes = [genome[i * BITS_PER_NOTE:i * BITS_PER_NOTE + BITS_PER_NOTE] for i in range(num_bars * num_notes)]

    note_length = 4 / float(num_notes)

    scl = EventScale(root=key, scale=scale, first=root)

    melody = {
        "notes": [],
        "velocity": [],
        "beat": []
    }

    # Takes the integers from "int_from_bits" and sends it to the main function to be sent to the pyo server.
    for note in notes:
        integer = int_from_bits(note)

        if not pauses:
            integer = int(integer % pow(2, BITS_PER_NOTE - 1))

        if integer >= pow(2, BITS_PER_NOTE - 1):
            melody["notes"] += [0]
            melody["velocity"] += [0]
            melody["beat"] += [note_length]
        else:
            if len(melody["notes"]) > 0 and melody["notes"][-1] == integer:
                melody["beat"][-1] += note_length
            else:
                melody["notes"] += [integer]
                melody["velocity"] += [127]
                melody["beat"] += [note_length]

    steps = []
    for step in range(num_steps):
        steps.append([scl[(note + step * 2) % len(scl)] for note in melody["notes"]])

    melody["notes"] = steps
    return melody


# This function is used to convert the genome to melody by sending it to the pyo server in the main function.
def genome_to_events(genome: Genome, num_bars: int, num_notes: int, num_steps: int,
                     pauses: bool, key: str, scale: str, root: int, bpm: int) -> [Events]:
    melody = genome_to_melody(genome, num_bars, num_notes, num_steps, pauses, key, scale, root)

    return [
        Events(
            midinote=EventSeq(step, occurrences=1),
            midivel=EventSeq(melody["velocity"], occurrences=1),
            beat=EventSeq(melody["beat"], occurrences=1),
            attack=0.001,
            decay=0.05,
            sustain=0.5,
            release=0.005,
            bpm=bpm
        ) for step in melody["notes"]
    ]


# Rating the melody genomes after they come to the "genome_to_events" function.
def fitness(genome: Genome, s: Server, num_bars: int, num_notes: int, num_steps: int,
            pauses: bool, key: str, scale: str, root: int, bpm: int) -> int:
    m = metronome(bpm)
    print("\nLets see if you like what the Algorithm cooked up for you!!!!!")
    print("You can rate the track between 0 and 5, cause you don't want the Algorithm to think that it created the "
          "next big banger!\n")
    events = genome_to_events(genome, num_bars, num_notes, num_steps, pauses, key, scale, root, bpm)
    for e in events:
        e.play()
    s.start()

    rating = int(input("How much would you rate this?\n"))

    for e in events:
        e.stop()
    s.stop()
    time.sleep(1)

    try:
        if rating > 5:
            print("!!!INVALID RATING!!!\n Setting rating to 5.")
    except ValueError:
        rating = 5

    return rating


# Plays the metronome
def metronome(bpm: int):
    met = Metro(time=1 / (bpm / 60.0)).play()
    t = CosTable([(0, 0), (50, 1), (200, .3), (500, 0)])
    amp = TrigEnv(met, table=t, dur=.25, mul=1)
    freq = Iter(met, choice=[660, 440, 440, 440])
    return Sine(freq=freq, mul=amp).mix(2).out()


# Saves all the melodies to MIDI files in a directory in a best to worst order.
def save_genome_to_midi(filename: str, genome: Genome, num_bars: int, num_notes: int, num_steps: int,
                        pauses: bool, key: str, scale: str, root: int, bpm: int):
    melody = genome_to_melody(genome, num_bars, num_notes, num_steps, pauses, key, scale, root)

    if len(melody["notes"][0]) != len(melody["beat"]) or len(melody["notes"][0]) != len(melody["velocity"]):
        raise ValueError

    mf = MIDIFile(1)

    track = 0
    channel = 0

    time = 0.0
    mf.addTrackName(track, time, "Sample Track")
    mf.addTempo(track, time, bpm)

    for i, vel in enumerate(melody["velocity"]):
        if vel > 0:
            for step in melody["notes"]:
                mf.addNote(track, channel, step[i], time, melody["beat"][i], vel)

        time += melody["beat"][i]

    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "wb") as f:
        mf.writeFile(f)


@click.command()
# Number of bars, default value is 4.
@click.option("--num-bars", default=4, prompt='How many number of bars do you want in your track, not sure? nevermind '
                                              'the default value will save you\n', type=int)
# Number of notes per bar, default is 8.
@click.option("--num-notes", default=8, prompt='\nHow many notes per bar do you need?? Unsure??? Just click enter and '
                                               'the default value will select a value for you\n', type=int)
# Number of steps (asks you whether you want to generate chords or just melodies).
@click.option("--num-steps", default=1, prompt='\nNumber of steps, pssttt the default value will make an 8-bit melody '
                                               'for you, you can use any other number other than 1\n', type=int)
# Asks you whether you want to introduce pauses.
@click.option("--pauses", default=False, prompt='\nDo you like pauses in your melodies??\n', type=bool)
# Asks you the key you wan the melody to be in, default key is C.
@click.option("--key", default="C", prompt='\nChoose the Key you want your melody too be in, there is already a '
                                           'default value preset\n',
              type=click.Choice(KEYS, case_sensitive=False))
# Asks you the scale of the melody and the default value is a major.
@click.option("--scale", default="major", prompt='\nWhat Scale do you want your melody to be in, default value is '
                                                 'already set\n',
              type=click.Choice(SCALES, case_sensitive=False))
# How high should the scale go, default is 4 octaves high.
@click.option("--root", default=4, prompt='\nChoose your Octave, How high do you want the scale to go??\n', type=int)
# How many different melodies should be generated, default value is 4.
@click.option("--population-size", default=4, prompt='\nHow many melodies do you want in each population?\n', type=int)
# How many mutations should each generation have, default value is 2.
@click.option("--num-mutations", default=2, prompt='\nNumber of mutations (Yeah, your beat is now a part of the '
                                                   'X-Men)\n', type=int)
# The probability of mutating a random node, default probability is 50%.
@click.option("--mutation-probability", default=0.5, type=float)
# BPM of the song, default value is 128bpm.
@click.option("--bpm", default=128, prompt='\n128 is the standard bpm, but you can increase or decrease it\n',
              type=int)
# All the above options are injected into the main function below.
def main(num_bars: int, num_notes: int, num_steps: int, pauses: bool, key: str, scale: str, root: int,
         population_size: int, num_mutations: int, mutation_probability: float, bpm: int):
    # This creates a folder where all the MIDI files are stored.
    folder = str(int(datetime.now().timestamp()))
    # Here we start to generate a random genome melody.
    population = [generate_genome(num_bars * num_notes * BITS_PER_NOTE) for _ in range(population_size)]
    # This server refers to the pyo library server, which is required to be initiated to generate sounds.
    s = Server().boot()

    population_id = 0
    # Asks whether you want to continue generating melodies in the next generation.
    running = True
    while running:
        # All the generated genomes are shuffled and put in a random order.
        random.shuffle(population)
        # Evaluates the fitness of the current genome. This "population_fitness" is sent over to the fitness function
        # and then we rate it.
        population_fitness = [
            (genome, fitness(genome, s, num_bars, num_notes, num_steps, pauses, key, scale, root, bpm)) for genome in
            population]
        # Here we sort it.
        sorted_population_fitness = sorted(population_fitness, key=lambda e: e[1], reverse=True)
        # Now we generate our new generation.
        population = [e[0] for e in sorted_population_fitness]
        # here we just take two elements from the previous generation and just put them in the next generation.
        next_generation = population[0:2]

        # We take the number of the population divide it by 2 and minus 1 from it, to get genomes for the parents
        # of the next generation.
        for j in range(int(len(population) / 2) - 1):

            def fitness_lookup(genome):
                for e in population_fitness:
                    if e[0] == genome:
                        return e[1]
                return 0

            parents = selection_pair(population, fitness_lookup)
            # "single_point_crossover" it takes a single node from each parents and puts it into the offspring
            offspring_a, offspring_b = single_point_crossover(parents[0], parents[1])
            # Here we just mutate both the offsprings.
            offspring_a = mutation(offspring_a, num=num_mutations, probability=mutation_probability)
            offspring_b = mutation(offspring_b, num=num_mutations, probability=mutation_probability)
            next_generation += [offspring_a, offspring_b]

        print(f"\nPopulation {population_id} done.")

        # This is how we send our genomes to the pyo server to get converted into music.
        events = genome_to_events(population[0], num_bars, num_notes, num_steps, pauses, key, scale, root, bpm)
        for e in events:
            e.play()
        s.start()
        input("\nHere is your highest rated track...")
        s.stop()
        for e in events:
            e.stop()

        time.sleep(1)

        events = genome_to_events(population[1], num_bars, num_notes, num_steps, pauses, key, scale, root, bpm)
        for e in events:
            e.play()
        s.start()
        input("\nHere is your second highest rated track...")
        s.stop()
        for e in events:
            e.stop()

        time.sleep(1)

        # Here is where the saving the audio file to MIDI happens.
        download = str(input("\nDo you want to save the entire population midi? [yes/no]: "))
        if download == "yes":
            for i, genome in enumerate(population):
                save_genome_to_midi(f"{folder}/{population_id}/{key}-{scale}-{bpm}-{i}.mid", genome, num_bars,
                                    num_notes,
                                    num_steps, pauses, key, scale, root, bpm)
            print("\nDone!!")
        elif download == "no":
            print("\nPopulation will not be downloaded!")
        else:
            print("Type yes or no")

        running = input("\nDo you want to continue to the next generation? [yes/no]: ")
        if running == "yes":
            population = next_generation
            population_id += 1
        elif running == "no":
            feedback = input("\nWas the algorithm able to make something that you liked? [yes/no]: ")
            if feedback == "yes":
                print("\nThat's fantastic!!")
                exit()
            elif feedback == "no":
                print("\nI'm sorry that you couldn't find what you were looking for!!!")
                exit()
            else:
                print("Please enter yes or no.")
        else:
            print("Please enter yes or no.")


if __name__ == '__main__':
    print(
        "!!!Welcome to SoundForge!!!\nSoundForge works with a Genetic algorithm, to help you generate tracks and save "
        "them as midi files on your local storage.\nThere is no limit to the number of populations (Populations are "
        "basically the number of track you want to generate at once in one iteration) you can generate,"
        " not satisfied with the results of this population that much, no worries, the next population is waiting"
        " for you!\n")

    print("The entire customization of the track is in your hands, you choose the scale, the key, the bpm, the number "
          "of bars, and much more, but dont worry if you arent familiar with any of this stuff, the inputs already "
          "have a preset value that generates 8-bit music.\n")
    main()
