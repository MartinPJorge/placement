library(mecgen)
library(SDMTools)
library(stringr)

# Read the micro cells
cells <- read.csv(file="fixed-cells/valencia-haven/valencia-haven-aaus.csv", header=TRUE, sep = ',')




# Obtain the link and nodes frames
assocs <- build5GScenario(lats = cells$lat, lons = cells$lon)
m1Assoc <- assocs[[1]]
m1Coords <- assocs[[2]]
m1AccAssocs <- assocs[[3]]
accCentCoords <- assocs[[4]]
m2Assocs <- assocs[[5]]
m2Switches <- assocs[[6]]
m2AggAssocs <- assocs[[7]]
aggCentCoords <- assocs[[8]]
m3Assocs <- assocs[[9]]
m3Switches <- assocs[[10]]


# Create the frames
frames <- graphFrames(m1Assoc, m1Coords, m1AccAssocs, accCentCoords,
                      m2Assocs, m2Switches, m2AggAssocs, aggCentCoords,
                      m3Assocs, m3Switches)

# Specify LTE and NR properties
nr_nodes <- c()
lte_nodes <- c()
cell_nodes <- frames$nodes
for (i in 1:nrow(cell_nodes)) {
  if (cell_nodes[i,]$type == 'cell') {
    cell_num <- as.numeric(str_extract(as.character(cell_nodes[i,]$id),
                                       regex('\\d+')))
    if (cell_num > 36)
      lte_nodes <- c(lte_nodes, as.character(cell_nodes[i,]$id))
    else
      nr_nodes <- c(nr_nodes, as.character(cell_nodes[i,]$id))
  }
}
newNodes <- addNodeProps(nodes = frames$nodes, id_ = nr_nodes,
                     properties = list(size=rep('nr', length(nr_nodes)),
                                       coverageRadius=
                                         rep(700, length(nr_nodes)),
                                       delay=rep(0.75, length(nr_nodes)),
                                       cost=rep(11, length(nr_nodes))))
newNodes <- addNodeProps(nodes = newNodes, id_ = lte_nodes,
                     properties = list(size=rep('lte', length(lte_nodes)),
                                       coverageRadius=
                                         rep(8000, length(lte_nodes)),
                                       delay=rep(5, length(lte_nodes)),
                                       cost=rep(5.5, length(lte_nodes))))
frames$nodes <- newNodes


# Attach edge servers
attachFrames <- attachServers(nodes = frames$nodes, links = frames$links,
                              numServers = 6,
                              bandwidth = 12,
                              bandwidthUnits = "Mbps",
                              distance = 0,
                              distanceUnits = "meter",
                              switchType = "m1",
                              properties = list(cpu=12, mem=20, disk=100,
                                                cost=5.83),
                              idPrefix = "edge_server")


# Attach cloud servers
attachFrames <- attachServers(nodes = attachFrames$nodes,
                              links = attachFrames$links,
                              numServers = 2,
                              bandwidth = 12,
                              bandwidthUnits = "Mbps",
                              distance = 0,
                              distanceUnits = "meter",
                              switchType = "m3",
                              properties = list(cpu=200, mem=200, disk=1000,
                                                cost=2.48),
                              idPrefix = "cloud_server")


######### THE SQUARE WHERE FOG NODES APPEAR #########
square1 <- data.frame(tl_lat=39.430355, tl_lon=-0.325356,
                      br_lat=39.427081, br_lon=-0.316449)
squares <- square1


######## GENERATE THE FOG NODES #######
robots_per_square <- 10
mesh_robot_connections <- ncol(combn(rep(0,robots_per_square), 2))
from_sqs <- data.frame(matrix(0, ncol = nrow(squares),
                              nrow = mesh_robot_connections))
to_sqs <- data.frame(matrix(0, ncol = nrow(squares),
                               nrow = mesh_robot_connections))
for (i in 1:nrow(squares)) {
  tos <- c()
  froms <- c()
  square <- squares[i,]
  prefix <- paste("robot_sq", i, sep="")
  attachFrames <- attachFogNodes(nodes = attachFrames$nodes,
                                 links = attachFrames$links,
                                 latB = square$br_lat, latT = square$tl_lat,
                                 lonL = square$tl_lon, lonR = square$br_lon,
                                 numNodes = robots_per_square,
                                 properties = list(cpu = 2, mem = 1, disk=10,
                                                   cost=15.27),
                                 bandwidth = 20, bandwidthUnits = "Mpbs",
                                 idPrefix = prefix)
  
  # Remove the links of the fog nodes
  attachFrames$links <- head(attachFrames$links,
                             nrow(attachFrames$links) - robots_per_square)
  
  # Connect fog nodes among them
  last_robot_ids <- as.vector(tail(attachFrames$nodes, robots_per_square)$id)
  robot_pairs <- combn(last_robot_ids, 2)
  for (c in 1:ncol(robot_pairs)) {
    link <- tail(attachFrames$links, 1)
    link$from <- robot_pairs[1,c]
    link$to <- robot_pairs[2,c]
    
    # Include the robot link in the connectivity data.frame
    froms <- c(froms, link$from)
    tos <- c(tos, link$to)
    
    # Get robot coordinates
    from_row <- as.numeric(rownames(subset(attachFrames$nodes, id==link$from)))
    from_lon <- attachFrames$nodes[from_row,]$lon
    from_lat <- attachFrames$nodes[from_row,]$lat
    to_row <- as.numeric(rownames(subset(attachFrames$nodes, id==link$to)))
    to_lon <- attachFrames$nodes[to_row,]$lon
    to_lat <- attachFrames$nodes[to_row,]$lat
    
    # Attach the robot with its distances
    link$distance <- SDMTools::distance(lat1 = to_lat, lon1 = to_lon,
                                        lat2 = from_lat,
                                        lon2 = from_lon)$distance
    attachFrames$links <- rbind(attachFrames$links, link)
    
  }
  
  # Specify the meshed connections delays of robots inside the square
  from_sqs[,i] <- froms
  to_sqs[,i] <- tos
  
  # Attach endpoint node
  square_endpoint <- paste("endpoint_sq", i, sep="")
  last_node <- tail(attachFrames$nodes, 1)
  last_robot <- tail(attachFrames$nodes, 1)
  last_link <- tail(attachFrames$links, 1)
  #
  last_node$id <- square_endpoint
  last_node$type <- 'endpoint'
  last_node$cpu <- 0
  last_node$mem <- 0
  last_node$disk <- 0
  attachFrames$nodes <- rbind(attachFrames$nodes, last_node)
  #
  last_link$from <- square_endpoint
  last_link$to <- last_robot$id
  attachFrames$links <- rbind(attachFrames$links, last_link)
  
  # Attach one endpoint at each level
  # to M1
  square_endpoint <- paste("endpoint_m1_sq", i, sep="")
  last_node$id <- square_endpoint
  attachFrames$nodes <- rbind(attachFrames$nodes, last_node)
  last_link$from <- square_endpoint
  last_link$to <- 'm1_0'
  attachFrames$links <- rbind(attachFrames$links, last_link)
  # to M2
  square_endpoint <- paste("endpoint_m2_sq", i, sep="")
  last_node$id <- square_endpoint
  attachFrames$nodes <- rbind(attachFrames$nodes, last_node)
  last_link$from <- square_endpoint
  last_link$to <- 'm2_0'
  attachFrames$links <- rbind(attachFrames$links, last_link)
  # to M3
  square_endpoint <- paste("endpoint_m3_sq", i, sep="")
  last_node$id <- square_endpoint
  attachFrames$nodes <- rbind(attachFrames$nodes, last_node)
  last_link$from <- square_endpoint
  last_link$to <- 'm3_0'
  attachFrames$links <- rbind(attachFrames$links, last_link)
}

######### SET THE D2D DELAY BETWEEN ROBOTS #########
d2d_delay <- 0.2 # ms
for (i in 1:nrow(squares)) {
  newLinks <- addLinkProps(links = attachFrames$links, from_ = from_sqs[,i],
                           to_ = to_sqs[,i],
                           properties = list(delay=rep(d2d_delay,
                                                       nrow(from_sqs))))
  attachFrames$links <- newLinks
}



######### SET FIXED INFRA DELAYS ASSUMING FIBER #########
froms <- c()
tos <- c()
delays <- c()
for (row in 1:nrow(attachFrames$links)) {
  from_id <- as.character(attachFrames$links[row,]$from)
  to_id <- as.character(attachFrames$links[row,]$to)
  distance <- as.numeric(attachFrames$links[row,]$distance)
  
  is_src_robot <- grepl("robot", from_id)
  is_dst_robot <-  grepl("robot", to_id)
  
  if (!is_src_robot && !is_dst_robot) {
    froms <- c(froms, from_id)
    tos <- c(tos, to_id)
    delays <- c(delays, distance / 3e5) # delay is in ms, distance in M, light
  }
}
newLinks <- addLinkProps(links = attachFrames$links, from_ = froms, to_ = tos,
                         properties = list(delay=delays))
attachFrames$links <- newLinks




# Generate the fiber hops delay, which include the processing delay of switches
fiber_delays <- read.csv('fiber_delays.csv', header = FALSE)
froms <- c()
tos <- c()
delays <- c()
for (row in 1:nrow(attachFrames$links)) {
  from <- as.character(attachFrames$links[row,]$from)
  to <- as.character(attachFrames$links[row,]$to)
  
  is_src_cell <-  grepl("cell", from)
  is_src_m1 <-  grepl("m1", from)
  is_dst_m1 <-  grepl("m1", to)
  is_src_m2 <-  grepl("m2", from)
  is_dst_m2 <-  grepl("m2", to)
  is_src_m3 <-  grepl("m3", from)
  is_dst_m3 <-  grepl("m3", to)
  
  if ((is_src_cell && is_dst_m1) ||
      (is_src_m1 && is_dst_m1) ||
      (is_src_m1 && is_dst_m2) ||
      (is_src_m2 && is_dst_m2) ||
      (is_src_m2 && is_dst_m2) ||
      (is_src_m3 && is_dst_m3)) {
    
    print('in')
    
    froms <- c(froms, from)
    tos <- c(tos, to)
    rand_delay <- runif(1, min=1, max=nrow(fiber_delays))
    delays <- c(delays, fiber_delays[rand_delay, ]) # delay is in ms
  }
}
newLinks <- addLinkProps(links = attachFrames$links, from_ = froms, to_ = tos,
                         properties = list(delay=delays))
attachFrames$links <- newLinks



# Store the generated graph
links <- attachFrames$links
nodes <- attachFrames$nodes
g = igraph::graph_from_data_frame(links, vertices = nodes, directed = FALSE)
igraph::write_graph(graph = g, file = "/tmp/infra.gml", format = "gml")

