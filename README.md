# TokyoMetro

The Tokyo Metro Route Finder is a project that implements Dijkstra's algorithm on a graph representation of the Tokyo metro system. The purpose of this project is to find the shortest route between two stations and provide clear instructions to users in understandable English. The front-end interface is supported by Streamlit, a Python library for creating interactive web applications.

## Features

### Graph Representation:

The Tokyo metro system is represented as a graph, where each station is a node and each connection between stations is an edge. This graph representation allows efficient computation of the shortest route using Dijkstra's algorithm.

### Dijkstra's Algorithm:

The project utilizes Dijkstra's algorithm to find the shortest path between two stations in the Tokyo metro system. Dijkstra's algorithm guarantees finding the optimal path based on the shortest distance.

### Instructions in English:

The project outputs clear and concise instructions in English to guide users through the shortest route. This ensures that users, including non-native English speakers or tourists, can easily navigate the Tokyo metro system.

### PyWebIO Interface:

The front-end interface of the project is built using PyWebIO, a user-friendly library for creating web applications. The Streamlit interface provides an intuitive and interactive experience for users to input their desired start and end stations and receive instructions.


## Dependencies

Please install python and pipenv if not installed already. Open your terminal and navigate to the directory in which this repository is cloned. Then run "pipenv install"

## How to Run

Open your terminal and run python3 programs/app.py