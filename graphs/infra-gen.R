library(mecgen)
library(SDMTools)

# Obtain the cells of Cobo Calleja
coboCells <- mecgen::cobo
coboCells <- head(coboCells, 20)
assocs <- build5GScenario(lats = coboCells$lat, lons = coboCells$lon)

# Obtain the link and nodes frames
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
frames <- graphFrames(m1Assoc, m1Coords, m1AccAssocs, accCentCoords,
                      m2Assocs, m2Switches, m2AggAssocs, aggCentCoords,
                      m3Assocs, m3Switches)
  

# Attach edge servers
attachFrames <- attachServers(nodes = frames$nodes, links = frames$links,
                              numServers = 6,
                              bandwidth = 12,
                              bandwidthUnits = "Mbps",
                              distance = 0,
                              distanceUnits = "meter",
                              switchType = "m1",
                              properties = list(cpu=2, mem=20, disk=100),
                              idPrefix = "edge_server")


# Attach cloud servers
attachFrames <- attachServers(nodes = frames$nodes, links = frames$links,
                              numServers = 2,
                              bandwidth = 12,
                              bandwidthUnits = "Mbps",
                              distance = 0,
                              distanceUnits = "meter",
                              switchType = "m3",
                              properties = list(cpu=20, mem=200, disk=1000),
                              idPrefix = "cloud_server")

######### THE TWO SQUARES WHERE FOG NODES APPEAR #########
# # left square
# tl = list(lat=40.266662, lon=-3.756308)
# br = list(lat=40.262594, lon=-3.751914)
# # right square
# tl2 = list(lat=40.264600, lon=-3.751753)
# br2 = list(lat=40.260469, lon=-3.748170)
square1 <- data.frame(tl_lat=40.266662, tl_lon=-3.756308,
                      br_lat=40.262594, br_lon=-3.751914)
square2 <- data.frame(tl_lat=40.264600, tl_lon=-3.751753,
                      br_lat=40.260469, br_lon=-3.748170)
squares <- rbind(square1, square2)


######## GENERATE THE FOG NODES #######
robots_per_square <- 10
for (i in 1:nrow(squares)) {
  square <- squares[i,]
  prefix <- paste("robot_sq", i, sep="")
  attachFrames <- attachFogNodes(nodes = attachFrames$nodes,
                                 links = attachFrames$links,
                                 latB = square$br_lat, latT = square$tl_lat,
                                 lonL = square$tl_lon, lonR = square$br_lon,
                                 numNodes = robots_per_square,
                                 properties = list(cpu = 1, mem = 1, disk=10),
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
    attachFrames$links <- rbind(attachFrames$links, link)
  }
  
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
}


# Store the generated graph
links <- attachFrames$links
nodes <- attachFrames$nodes
g = igraph::graph_from_data_frame(links, vertices = nodes, directed = FALSE)
igraph::write_graph(graph = g, file = "/tmp/infra.gml", format = "gml")

