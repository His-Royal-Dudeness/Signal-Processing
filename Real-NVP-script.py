import numpy as np
import tensorflow as tf
import tensorflow_probability as tfp

from sklearn.datasets import make_moons
data = make_moons(10000, noise=0.05)[0]

epochs = 1000
num_of_layers = 3
num_of_cells = 8
learning_rate = 5e-2
num_of_complete_batches = 10

num_of_features = int(data.shape[1])
net_size = [num_of_features, num_of_cells, num_of_layers]

def glorot_init(shape):
    return tf.Variable(tf.cast(tf.random.normal(shape=shape, stddev=1. / tf.sqrt(shape[0] / 2.), seed=0), dtype=tf.float64))

def printer(loss, epoch):
    print('epoch: ' + str(epoch.numpy()) + '  loss: ' + str(np.round(loss.numpy(), 6)))
    return loss

#creating dictionaries for weights and biases
weights = dict()
biases = dict()
for i in range(num_of_cells):
    for j in range(num_of_layers - 1):
        weights['s_up' + str(i) + str(j)] = glorot_init(
            [int(np.floor(num_of_features / 2)), int(np.floor(num_of_features / 2))])
        biases['s_up' + str(i) + str(j)] = glorot_init([int(np.floor(num_of_features / 2))])
        weights['s_down' + str(i) + str(j)] = glorot_init(
            [int(np.ceil(num_of_features / 2)), int(np.ceil(num_of_features / 2))])
        biases['s_down' + str(i) + str(j)] = glorot_init([int(np.ceil(num_of_features / 2))])

        weights['t_up' + str(i) + str(j)] = glorot_init(
            [int(np.floor(num_of_features / 2)), int(np.floor(num_of_features / 2))])
        biases['t_up' + str(i) + str(j)] = glorot_init([int(np.floor(num_of_features / 2))])
        weights['t_down' + str(i) + str(j)] = glorot_init(
            [int(np.ceil(num_of_features / 2)), int(np.ceil(num_of_features / 2))])
        biases['t_down' + str(i) + str(j)] = glorot_init([int(np.ceil(num_of_features / 2))])

    # this part is necessary when the number of features is odd so that the ceil and floor methods won't mix up.
    # if the number of features is even, then it would have been enough to change line 41 into:
    # for j in range(self.num_of_layers): - and erase the next part.
    if num_of_layers == 1:
        j = 0
    else:
        j = j + 1
    weights['s_up' + str(i) + str(j)] = glorot_init(
        [int(np.floor(num_of_features / 2)), int(np.ceil(num_of_features / 2))])
    biases['s_up' + str(i) + str(j)] = glorot_init([int(np.ceil(num_of_features / 2))])
    weights['s_down' + str(i) + str(j)] = glorot_init(
        [int(np.ceil(num_of_features / 2)), int(np.floor(num_of_features / 2))])
    biases['s_down' + str(i) + str(j)] = glorot_init([int(np.floor(num_of_features / 2))])

    weights['t_up' + str(i) + str(j)] = glorot_init(
        [int(np.floor(num_of_features / 2)), int(np.ceil(num_of_features / 2))])
    biases['t_up' + str(i) + str(j)] = glorot_init([int(np.ceil(num_of_features / 2))])
    weights['t_down' + str(i) + str(j)] = glorot_init(
        [int(np.ceil(num_of_features / 2)), int(np.floor(num_of_features / 2))])
    biases['t_down' + str(i) + str(j)] = glorot_init([int(np.floor(num_of_features / 2))])

    def NN(batch, key, num_of_layers, weights, biases):
        for k in range(num_of_layers):
            if k==num_of_layers-1:
                batch = tf.nn.dropout(tf.matmul(batch, weights[key + str(k)]) + biases[key + str(k)], rate=0.00)
            else:
               batch = tf.nn.dropout(tf.nn.sigmoid(tf.matmul(batch, weights[key + str(k)]) + biases[key + str(k)]), rate=0.00)
        return batch
    NN_func = tf.function(NN)

    def forward_pass(batch_x, num_of_features, num_of_cells, weights, biases):
        sum_log_s = 0
        #dividing the input into 2 equal parts (if the input size is odd, than the lower part is larger by 1).
        batch_1 = batch_x[:, 0:int(np.floor(num_of_features / 2))]
        batch_2 = batch_x[:, int(np.floor(num_of_features / 2)):]
        #computing the s & t that each cell outputs for the upper and lower part
        for j in range(num_of_cells):
            #using the upper input to compute s_down & t_down
            # log_s_down = (1-tf.nn.relu(self.NN_func(batch_1, 's_up' + str(j))))/self.num_of_features
            log_s_down = tf.tanh(NN_func(batch_1, 's_up' + str(j), num_of_layers, weights, biases))#/self.num_of_features
            t_down = tf.tanh(NN_func(batch_1, 't_up' + str(j), num_of_layers, weights, biases))
            y_2 = tf.multiply(batch_2, tf.exp(log_s_down)) + t_down
            #using the output of the above to comupte s_up & t_up - that way we keep the determinant of the Jacobian simple
            #and still "mix" the features in every iteration
            # log_s_up = (1-tf.nn.relu(self.NN_func(y_2, 's_down' + str(j))))/self.num_of_features
            log_s_up = tf.tanh(NN_func(y_2, 's_down' + str(j), num_of_layers, weights, biases))#/self.num_of_features
            t_up = tf.tanh(NN_func(y_2, 't_down' + str(j), num_of_layers, weights, biases))
            y_1 = tf.multiply(batch_1, tf.exp(log_s_up)) + t_up

            batch_1 = y_1
            batch_2 = y_2

            sum_log_s = sum_log_s + tf.reduce_sum(log_s_down, 1) + tf.reduce_sum(log_s_up, 1)


        batch_x = tf.concat([y_1, y_2], 1)
        return batch_x, sum_log_s
    forward_pass_func = tf.function(forward_pass)

    def optimize(batch_x, weights, biases ,optimizer, dist, num_of_features, num_of_cells):
        with tf.GradientTape() as g:
            l2_reg = tf.reduce_sum(0.0000002 * tf.square([r for r in weights.values()]))
            curr_y, sum_log_s = forward_pass_func(batch_x, num_of_features, num_of_cells, weights, biases)
            #the loss is log of the likelihood in the latent space. (including the determinant of the jacobian).
            loss = -tf.reduce_mean(tf.cast(dist.log_prob(tf.cast(curr_y, tf.float32)), tf.float64) + sum_log_s, 0)+l2_reg
        trainable_variables = [[r for r in weights.values()] + [r for r in biases.values()]][0]
        gradients = g.gradient(loss, trainable_variables)
        optimizer.apply_gradients(zip(gradients, trainable_variables))
        return loss
    optimize_func = tf.function(optimize)

dist = tfp.distributions.MultivariateNormalDiag(loc=[0.0] * num_of_features,
                                                 scale_diag=[1.0] * num_of_features)
optimizer = tf.optimizers.Adam(learning_rate=learning_rate)

batch_size = int(len(data) / num_of_complete_batches)
residual = len(data) % batch_size

for epoch in range(epochs):
    extra = 0
    for batch in range(num_of_complete_batches):
        if batch == num_of_complete_batches - 1:
            extra = int(residual)
        batch_x = data[batch * batch_size:((batch + 1) * batch_size) + extra]
        ll = optimize_func(batch_x, weights, biases ,optimizer, dist, num_of_features, num_of_cells)
    # # printing the loss of the last batch every 10 epoches
    if epoch % 10 == 0:
        tf.py_function(func=printer, inp=[ll, epoch], Tout=tf.float64)

def generate(batch_x, num_of_features, num_of_cells, weights, biases):
    sum_log_s = 0
    # dividing the input into 2 equal parts (if the input size is odd, than the lower part is larger by 1).
    batch_1 = batch_x[:, 0:int(np.floor(num_of_features / 2))]
    batch_2 = batch_x[:, int(np.floor(num_of_features / 2)):]
    # computing the s & t that each cell outputs for the upper and lower part
    for j in range(num_of_cells - 1, -1, -1):
        # using the output of the above to comupte s_up & t_up - that way we keep the determinant of the Jacobian simple
        # and still "mix" the features in every iteration
        # log_s_up = (1-tf.nn.relu(self.NN_func(y_2, 's_down' + str(j))))/self.num_of_features
        log_s_up = tf.tanh(NN_func(batch_2, 's_down' + str(j), num_of_layers, weights, biases))  # /self.num_of_features
        t_up = tf.tanh(NN_func(batch_2, 't_down' + str(j), num_of_layers, weights, biases))
        y_1 = tf.multiply((batch_1 - t_up), 1 / tf.exp(log_s_up))
        # using the upper input to compute s_down & t_down
        # log_s_down = (1-tf.nn.relu(self.NN_func(batch_1, 's_up' + str(j))))/self.num_of_features
        log_s_down = tf.tanh(NN_func(y_1, 's_up' + str(j), num_of_layers, weights, biases))  # /self.num_of_features
        t_down = tf.tanh(NN_func(y_1, 't_up' + str(j), num_of_layers, weights, biases))
        y_2 = tf.multiply((batch_2 - t_down), 1 / tf.exp(log_s_down))

        batch_1 = y_1
        batch_2 = y_2

        sum_log_s = sum_log_s + tf.reduce_sum(log_s_down, 1) + tf.reduce_sum(log_s_up, 1)

    batch_x = tf.concat([y_1, y_2], 1)
    return batch_x

print('***')
