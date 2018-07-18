import numpy as np
import tensorflow as tf
import tensorflow.contrib.layers as layers

def normalized_columns_initializer(std=1.0):
    def _initializer(shape, dtype=None, partition_info=None):
        out = np.random.randn(*shape).astype(np.float32)
        out *= std / np.sqrt(np.square(out).sum(axis=0, keepdims=True))
        return tf.constant(out)
    return _initializer

def make_convs(inpt, convs, padding, scope='convnet', reuse=None):
    out = inpt
    with tf.variable_scope(scope, reuse=reuse):
        for num_outputs, kernel_size, stride in convs:
            out = layers.convolution2d(
                out,
                num_outputs=num_outputs,
                kernel_size=kernel_size,
                stride=stride,
                padding=padding,
                activation_fn=tf.nn.elu
            )
    return out

def make_network(convs,
                 fcs,
                 padding,
                 lstm,
                 inpt,
                 action,
                 reward,
                 rnn_state_tuple,
                 num_actions,
                 lstm_unit,
                 scope,
                 reuse=None):
    with tf.variable_scope(scope, reuse=reuse):
        out = make_convs(inpt, convs, padding)

        out = layers.flatten(out)

        with tf.variable_scope('hiddens'):
            for hidden in fcs:
                out = layers.fully_connected(
                    out, hidden, activation_fn=tf.nn.relu)

        reward = tf.reshape(reward, [-1, 1])
        out = tf.concat([out, action, reward], axis=1)

        with tf.variable_scope('rnn'):
            lstm_cell = tf.contrib.rnn.BasicLSTMCell(lstm_unit, state_is_tuple=True)
            rnn_in = tf.expand_dims(out, [0])
            step_size = tf.shape(inpt)[:1]
            lstm_outputs, lstm_state = tf.nn.dynamic_rnn(
                lstm_cell, rnn_in, initial_state=rnn_state_tuple,
                sequence_length=step_size, time_major=False)
            rnn_out = tf.reshape(lstm_outputs, [-1, lstm_unit])

        if lstm:
            out = rnn_out

        policy = layers.fully_connected(
            out, num_actions, activation_fn=tf.nn.softmax,
            weights_initializer=normalized_columns_initializer(0.01),
            biases_initializer=None)

        value = layers.fully_connected(
            out, 1, activation_fn=None, biases_initializer=None,
            weights_initializer=normalized_columns_initializer())

    return policy, value, (lstm_state[0][:1, :], lstm_state[1][:1, :])
