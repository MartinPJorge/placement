library("igraph")

containers_graph <- read_graph('containers.gml', format='gml')
corners <- V(containers_graph)
corners_labels <- vertex_attr(containers_graph, name='label',
                              index = V(containers_graph))

# Number of container rows, for each column of containers
column_rows <- c(10, 14, 14, 14, 15, 15)
for (col in 1:length(column_rows)) {
  for (row in 1:length(column_rows[col])) {
    # PASS
  }
}

